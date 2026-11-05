"""Offline wrapper-specific experimental reconstruction; never runtime approval."""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from bounded import FLAGS, JDK, digest, run

HERE = Path(__file__).resolve().parent
TOOLS = ['maven-shade-plugin-3.6.2.jar','asm-9.9.1.jar','asm-commons-9.9.1.jar',
         'asm-tree-9.9.1.jar','plexus-utils-3.6.0.jar','slf4j-api-1.7.36.jar','maven-plugin-api-3.9.12.jar']
OLD = '1914fed4ed18999ce98ad844aa5d0b09f31027be329ffd82d861d6f7c6f097c7'
PAIRS = [('2.22.2','2.22.3')]
PROVENANCE = 'META-INF/cnc-parquet-jackson-fork.json'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def checked(path, expected):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'missing/linked input '+str(path))
    b = path.read_bytes()
    require(sha(b) == expected, 'input drift '+str(path))
    return b

def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')

def entries(path):
    with zipfile.ZipFile(path) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'ambiguous ZIP')
        return {i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}

def payload(path):
    # NOTICE is a whole-wrapper aggregate. Retain the original aggregate and
    # add the new component notices separately in explicit fork provenance.
    return {n:b for n,b in entries(path).items() if n not in {'META-INF/MANIFEST.MF','META-INF/NOTICE','META-INF/LICENSE','META-INF/DEPENDENCIES'}}

def validate_pins(pins):
    require(pins and len(pins)==len({p['file'] for p in pins}), 'empty/duplicate pins')
    for p in pins:
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',p['file']) and p['file'] not in ('.','..'), 'unsafe pin filename')
        require(re.fullmatch(r'[0-9a-f]{64}',p['sha256']), 'invalid pin digest')
        require(p['url'].startswith(('https://repo.maven.apache.org/maven2/',
          'https://raw.githubusercontent.com/apache/parquet-java/apache-parquet-1.18.1/')), 'untrusted pin URL')

def source_snapshot(source, expected):
    require(not any(p.is_symlink() for p in [source,*source.parents,*source.rglob('*')]), 'linked stock')
    actual = {p.relative_to(source).as_posix():digest(p) for p in source.rglob('*') if p.is_file()}
    require(actual==expected,'stock acquisition drift')
    return actual

def stock(source):
    lock = json.loads((HERE.parent/'stock-occurrences/source-lock.json').read_text())['archives']
    require(len(lock)==215 and len({r['path'] for r in lock})==215,'wrong stock scope')
    return source_snapshot(source,{r['path']:r['sha256'] for r in lock})

def source_files():
    return {p.name:digest(p) for p in HERE.iterdir() if p.is_file() and
      (p.suffix in ('.py','.java','.in') or p.name in ('pins.json','consumer-pins.json','support-lock.json'))}

def fresh_output(output, forbidden):
    output=output.absolute()
    require(not output.exists() and not output.is_symlink() and
      not any(p.is_symlink() for p in output.parents) and '.m2' not in output.parts and
      not any(output.is_relative_to(p.resolve()) for p in forbidden),'output must be fresh external cache')
    output.mkdir(parents=True)
    return output

def check_baseline(original, old_payload):
    mismatches=[n for n,b in old_payload.items() if original.get(n)!=b]
    require(not mismatches,'old Shade baseline mismatch '+str(mismatches[:8]))
    extras=[n for n in original if ('shaded/parquet/com/fasterxml/jackson/' in n or n.startswith('META-INF/maven/com.fasterxml.jackson.core/')) and n not in old_payload]
    require(not extras,'unmapped old Jackson entries '+str(extras[:8]))

def publish(path, data):
    require(not path.is_symlink(),'linked publication')
    with path.open('xb') as f:f.write(data)

class PreservedInfo(zipfile.ZipInfo):
    def _encodeFilenameFlags(self):
        # Python's default clears the UTF-8 bit for ASCII names when emitting
        # the central directory. Keep the acquired filename encoding flags.
        return self.filename.encode('utf-8' if self.flag_bits & 0x800 else 'cp437'), self.flag_bits

def assemble(original, remove, replacement, provenance):
    require(remove and replacement and remove <= set(entries(io.BytesIO(original))), 'invalid selected entries')
    require(any(entries(io.BytesIO(original)).get(n)!=b for n,b in replacement.items()),'no-op replacement')
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'ambiguous original')
        require(not any(re.match(r'META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|SIG-)', n, re.IGNORECASE) for n in z.namelist()), 'signed original')
        require(not re.search(rb'(?im)^\S*-Digest:', z.read('META-INF/MANIFEST.MF')), 'manifest signatures')
        require(PROVENANCE not in z.namelist(), 'already patched')
        require(not (set(replacement)-remove) & set(z.namelist()), 'replacement collision')
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as w:
            w.comment=z.comment
            infos=z.infolist()
            for index, info in enumerate(infos):
                if info.filename in remove:
                    continue
                acquired=info
                info=PreservedInfo(acquired.filename,acquired.date_time)
                for field in zipfile.ZipInfo.__slots__:
                    if hasattr(acquired,field):setattr(info,field,getattr(acquired,field))
                end=infos[index+1].header_offset if index+1<len(infos) else z.start_dir
                raw=original[info.header_offset:end]
                info.header_offset=w.fp.tell()
                w.fp.write(raw);w.filelist.append(info);w.NameToInfo[info.filename]=info
                w.start_dir=w.fp.tell();w._didModify=True
            for n,b in sorted(replacement.items()):
                i=zipfile.ZipInfo(n,(2026,11,5,0,0,0));i.external_attr=0o100644<<16
                w.writestr(i,b)
            i=zipfile.ZipInfo(PROVENANCE,(2026,11,5,0,0,0));i.external_attr=0o100644<<16
            w.writestr(i,json.dumps(provenance,sort_keys=True,indent=2).encode())
    result=out.getvalue()
    new=entries(io.BytesIO(result));old=entries(io.BytesIO(original))
    require(set(new)==(set(old)-remove)|set(replacement)|{PROVENANCE}, 'entry-set drift')
    require(all(new[n]==b for n,b in old.items() if n not in remove),'preserved content drift')
    def raw_records(data):
        with zipfile.ZipFile(io.BytesIO(data)) as r:
            infos=r.infolist()
            return {x.filename:data[x.header_offset:(infos[i+1].header_offset if i+1<len(infos) else r.start_dir)] for i,x in enumerate(infos)}
    a,b=raw_records(original),raw_records(result)
    require(all(b[n]==v for n,v in a.items() if n not in remove), 'preserved raw record drift')
    with zipfile.ZipFile(io.BytesIO(original)) as a, zipfile.ZipFile(io.BytesIO(result)) as b:
        fields = ['filename','date_time','create_system','create_version','extract_version',
                  'flag_bits','volume','internal_attr','external_attr','compress_type','CRC',
                  'compress_size','file_size','extra','comment']
        for n in set(a.namelist())-remove:
            require(all(getattr(a.getinfo(n),f)==getattr(b.getinfo(n),f) for f in fields),
                    'preserved central metadata drift '+n)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args()
    require(not any(x.is_symlink() for p in [a.cache.absolute(),a.source.absolute()] for x in [p,*p.parents]),'linked input root')
    cache=a.cache.resolve();source=a.source.resolve()
    require('.m2' not in cache.parts,'shared Maven repository forbidden')
    out=fresh_output(a.output,[HERE.parents[3],source,cache])
    pins=json.loads((HERE/'pins.json').read_text());validate_pins(pins)
    support=json.loads((HERE/'support-lock.json').read_text())
    for n,h in support.items():checked(HERE.parent/n,h)
    before={r['file']:sha(checked(cache/r['file'],r['sha256'])) for r in pins}
    inputs=source_files()
    jdk=json.loads((HERE.parent/'jackson/jdk21-pins.json').read_text())
    for n,h in jdk.items():checked(JDK/n,h)
    source_before=stock(source);save(out/'source-before.json',source_before)
    original=checked(cache/'parquet-jackson-1.18.1.jar',OLD)
    nar=source/'opt/nifi/nifi-current/lib/nifi-iceberg-parquet-writer-nar-2.12.0.nar'
    with zipfile.ZipFile(nar) as z:
        require(len(z.namelist())==len(set(z.namelist())),'ambiguous NAR')
        require(z.read('META-INF/bundled-dependencies/parquet-jackson-1.18.1.jar')==original,'stock/official mismatch')
    cp=':'.join(str(cache/n) for n in TOOLS)
    run([str(JDK/'bin/javac'),*['-J'+x for x in FLAGS],'-cp',cp,'-d',str(out),str(HERE/'Shade.java')],out/'compile-shade.log')
    remove=set();replacement={};baseline=[];notices={}
    for old,new in PAIRS:
        for v in [old,new]:
            name=f'jackson-{v}'
            target=out/(name+'-shaded.jar')
            libraries=[cache/f'jackson-core-{v}.jar',cache/'jackson-annotations-2.22.jar',cache/f'jackson-databind-{v}.jar']
            run([str(JDK/'bin/java'),*FLAGS,'-cp',str(out)+':'+cp,'Shade',str(target),*map(str,libraries)],out/(name+'.log'))
        old_payload=payload(out/f'jackson-{old}-shaded.jar')
        stock_entries=entries(io.BytesIO(original))
        mismatches=[n for n,b in old_payload.items() if stock_entries.get(n)!=b]
        save(out/'baseline.json',{'entries':len(old_payload),'mismatches':mismatches})
        check_baseline(stock_entries,old_payload)
        fixed=payload(out/f'jackson-{new}-shaded.jar')
        # Identical annotations, licenses and services retain acquired raw ZIP
        # records/central attributes. Only actual deltas are selected.
        remove={n for n,b in old_payload.items() if fixed.get(n)!=b}
        replacement={n:b for n,b in fixed.items() if old_payload.get(n)!=b}
        require(all(n in old_payload or n not in stock_entries for n in fixed),'unselected component collision')
        baseline.append({'old':old,'new':new,'old_entries_equal':len(old_payload)})
        notices={n:b.decode('utf-8') for n,b in entries(out/f'jackson-{new}-shaded.jar').items() if n in {'META-INF/LICENSE','META-INF/NOTICE'}}
    provenance={'original_sha256':OLD,'runtime_approved':False,'status':'experimental-wrapper-candidate',
                'baseline':baseline,'inputs':before,'candidate_source':inputs,'support':support,'new_component_notices':notices,
                'preserved':'all nonselected local ZIP records including services/native/manifest/annotations',
                'fork':'CNC local Parquet 1.18.1 Jackson reconstruction; not an Apache release'}
    candidate=assemble(original,remove,replacement,provenance)
    name='parquet-jackson-1.18.1-cnc-jackson.jar'
    save(out/'entry-delta.json',{'selected_original':{n:sha(stock_entries[n]) for n in sorted(remove)},'replacement':{n:sha(b) for n,b in sorted(replacement.items())},'preserved':{n:sha(b) for n,b in stock_entries.items() if n not in remove}})
    source_after=stock(source)
    save(out/'source-after.json',source_after)
    require(source_after==source_before,'stock changed')
    require({r['file']:sha(checked(cache/r['file'],r['sha256'])) for r in pins}==before,'cache changed')
    require(source_files()==inputs,'source changed')
    for n,h in jdk.items():checked(JDK/n,h)
    require({n:digest(HERE.parent/n) for n in support}==support,'support changed')
    publish(out/name,candidate)
    save(out/'summary.json',{'status':'experimental-wrapper-candidate-consumer-verification-pending','candidate':name,'candidate_sha256':sha(candidate),'runtime_approved':False,'source_archives':len(source_before),'originals_unchanged':True,'baseline':baseline,'removed_entries':len(remove),'replacement_entries':len(replacement),'inputs':before,'source':inputs,'jdk':jdk})
    print(out/name,sha(candidate))
if __name__=='__main__':main()
