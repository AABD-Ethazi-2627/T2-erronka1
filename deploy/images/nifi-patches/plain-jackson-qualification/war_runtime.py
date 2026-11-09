"""Disposable actual Jetty WAR loader/component probes; never an overlay."""
import argparse
import json
import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

import qualify as q

HERE=Path(__file__).resolve().parent
JAVA=Path('/usr/lib/jvm/java-21-openjdk/bin/java')
OPTIONS=['-Xmx256m','-XX:MaxMetaspaceSize=96m','-XX:MaxDirectMemorySize=32m','-XX:ReservedCodeCacheSize=32m','-XX:CompressedClassSpaceSize=32m','-XX:ActiveProcessorCount=1','-XX:-CreateCoredumpOnCrash']


EXPECTED_CONTEXTS = (
    ('nifi-jolt-nar', 'META-INF/bundled-dependencies/nifi-jolt-transform-json-ui-2.12.0.war'),
    ('nifi-server-nar', 'META-INF/bundled-dependencies/nifi-ui-2.12.0.war'),
    ('nifi-server-nar', 'META-INF/bundled-dependencies/nifi-web-api-2.12.0.war'),
    ('nifi-standard-content-viewer-nar', 'META-INF/bundled-dependencies/nifi-standard-content-viewer-2.12.0.war'),
    ('nifi-update-attribute-nar', 'META-INF/bundled-dependencies/nifi-update-attribute-ui-2.12.0.war'),
)


def no_links(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('linked input or output path')
    return path


def verify_input_file(path, expected):
    path = no_links(path)
    if not path.is_file() or q.file_sha(path) != expected:
        raise ValueError('input pin mismatch: ' + str(path))
    return expected


def read_metadata(path):
    data = json.loads(no_links(path).read_text())
    if (data.get('schema') != 1 or data.get('runtime_approved') is not False
        or data.get('promotion_eligible') is not False or 'replacement' not in data
        or data['replacement'] is not None):
        raise ValueError('input metadata must remain preparation only')
    return data


def select_contexts(inventory):
    if inventory.get('inventory_schema') != 2:
        raise ValueError('obsolete inventory')
    contexts = [c for c in inventory['contexts'] if c['war']]
    if [(c['id'], c['war']) for c in contexts] != list(EXPECTED_CONTEXTS):
        raise ValueError('WAR denominator drift')
    return contexts


def extract_war(archive, output, pins, cache, fixed):
    output = no_links(output)
    if output.exists():
        raise FileExistsError('existing WAR evidence: ' + str(output))
    seen, destinations, planned = set(), set(), []
    total = 0
    # Check the whole central inventory before writing any payload.
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if (info.filename in seen or path.is_absolute() or '..' in path.parts
            or '\\' in info.filename or '\x00' in info.filename
            or not info.filename or str(path) != info.filename.rstrip('/')):
            raise ValueError('ambiguous or escaping WAR member')
        seen.add(info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('special WAR member')
        if info.is_dir() and info.file_size:
            raise ValueError('directory WAR member contains payload')
        total += info.file_size
        if info.file_size > 96 * 1024**2 or total > 256 * 1024**2:
            raise ValueError('WAR extraction budget')
        if info.is_dir():
            continue
        selected = fixed and path.parent == PurePosixPath('WEB-INF/lib') and path.name in q.OLD_NEW
        target = path.with_name(q.OLD_NEW[path.name]) if selected else path
        if target in destinations:
            raise ValueError('duplicate effective WAR destination')
        destinations.add(target)
        planned.append((info, path, target, selected))
    for target in destinations:
        if any(parent in destinations for parent in target.parents):
            raise ValueError('file/directory WAR collision')
    output.mkdir(parents=True, exist_ok=False)
    changes = []
    for info, path, target, selected in planned:
        blob = archive.read(info)
        if len(blob) != info.file_size:
            raise ValueError('short WAR entry read')
        if (path.parent == PurePosixPath('WEB-INF/lib') and path.name in q.OLD_NEW
            and q.sha(blob) != pins[path.name]['sha256']):
            raise ValueError('old WAR JAR pin mismatch')
        if selected:
            new = q.OLD_NEW[path.name]
            source = no_links(cache / new)
            blob = source.read_bytes()
            if q.sha(blob) != pins[new]['sha256']:
                raise ValueError('fixed WAR JAR pin mismatch')
            changes.append({'old': path.name, 'new': new, 'sha256': q.sha(blob)})
        dest = output.joinpath(*target.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as handle:
            handle.write(blob)
    return changes


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--proof',type=Path,required=True);args=parser.parse_args()
    if not args.proof.is_absolute():raise ValueError('absolute proof root required')
    base=no_links(args.proof)
    if not base.is_dir():raise ValueError('existing proof root required')
    out=base/'jetty-runtime'
    if out.exists() or (base/'jetty-runtime-result.json').exists():raise FileExistsError('existing Jetty evidence')
    expected=read_metadata(HERE/'war-runtime-inputs.json')
    for name,digest in expected['proof_inputs'].items():verify_input_file(base/name,digest)
    for name,digest in expected['support_sources'].items():verify_input_file(HERE/name,digest)
    for name,digest in expected['system_inputs'].items():
        if q.file_sha(Path(name))!=digest:raise ValueError('system input pin mismatch: '+name)
    out.mkdir(exist_ok=False)
    inv=json.loads((base/'inventory.json').read_text())
    contexts=select_contexts(inv)
    rows={r['manifest']['Nar-Id']:r for r in inv['roots']}
    needed={i for c in contexts for i in [c['id'],*rows[c['id']]['parents']]}
    pins={p['file']:p for p in json.loads((base/'pins.json').read_text())}
    before={str(p):q.file_sha(p) for p in HERE.iterdir() if p.is_file()}
    before.update({str(base/n):q.file_sha(base/n) for n in ('inventory.json','pins.json')})
    before.update({name:q.file_sha(Path(name)) for name in expected['system_inputs']})
    report={'status':'started','replacement':None,'runtime_approved':False,'promotion_eligible':False,'sources_before':before,'commands':[],'contexts':contexts,'limits':['actual Jetty WebInfConfiguration and loader only; no server/servlet/filter/listener startup','one benign mapper roundtrip per WAR; only selected actual resolver bodies executed','not complete dynamic linkage/reflection/provider or NiFi/SMB acceptance']}
    def save():q.save(base/'jetty-runtime-result.json',report)
    def run(cmd,label,expected=0):
        with (out/(label+'.stdout')).open('x') as stdout,(out/(label+'.stderr')).open('x') as stderr:
            result=subprocess.run(list(map(str,cmd)),stdout=stdout,stderr=stderr,timeout=35,check=False,
                env={k:v for k,v in os.environ.items() if k not in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','MAVEN_OPTS')})
        report['commands'].append({'label':label,'command':list(map(str,cmd)),'returncode':result.returncode,'expected':expected});save()
        if (not expected and result.returncode) or (expected and not result.returncode):raise ValueError(label+' unexpected exit')
        return (out/(label+'.stdout')).read_text(),(out/(label+'.stderr')).read_text()
    save()
    try:
        top=out/'top';top.mkdir()
        for p in Path('/opt/nifi/nifi-current/lib').glob('*.jar'):
            before[str(p)]=q.file_sha(p);shutil.copyfile(p,top/p.name)
        cp=os.pathsep.join(str(p) for p in sorted(top.glob('*.jar')))
        classes=out/'classes';classes.mkdir()
        run(['/jdk/bin/javac',*['-J'+x for x in OPTIONS],'-cp',cp,'-d',classes,HERE/'NarProbe.java',HERE/'JettyWarProbe.java'],'compile')
        parents=out/'parents.tsv';parents.write_text(''.join(i+'\t'+rows[i]['manifest'].get('Nar-Dependency-Id','')+'\n' for i in sorted(needed)))
        for variant in ('old','fixed'):
            tree=out/variant
            for id in sorted(needed):
                row=rows[id];source=Path('/')/row['path']
                if q.file_sha(source)!=row['sha256']:raise ValueError('source NAR drift')
                before[str(source)]=row['sha256']
                leaf=tree/id/'NAR-INF/bundled-dependencies';leaf.mkdir(parents=True)
                with zipfile.ZipFile(source) as archive:
                    for name in q.jar_names(archive):
                        blob=archive.read(name);filename=Path(name).name
                        if filename in q.OLD_NEW and q.sha(blob)!=pins[filename]['sha256']:raise ValueError('source JAR pin mismatch')
                        if variant=='fixed' and filename in q.OLD_NEW:
                            filename=q.OLD_NEW[filename];blob=no_links(base/'cache'/filename).read_bytes()
                            if q.sha(blob)!=pins[filename]['sha256']:raise ValueError('candidate JAR pin mismatch')
                        with (leaf/filename).open('xb') as f:f.write(blob)
            for i,ctx in enumerate(contexts):
                family='3' if ctx['id']=='nifi-jolt-nar' else '2'
                version=('3.2.' if family=='3' else '2.22.')+('3' if variant=='fixed' else '2')
                war=tree/('war-'+str(i))
                with q.container(Path('/')/rows[ctx['id']]['path'],ctx['war']) as archive:
                    changes=extract_war(archive,war,pins,base/'cache',variant=='fixed')
                filename='jackson-databind-'+version+'.jar'
                if (war/'WEB-INF/lib'/filename).is_file():defining='WAR'
                else:
                    # Actual NAR parent-first order, including the context's own JARs.
                    order=list(reversed([ctx['id'],*rows[ctx['id']]['parents']]))
                    defining=next(x for x in order if (tree/x/'NAR-INF/bundled-dependencies'/filename).is_file())
                consumers = {
                    'nifi-web-api-2.12.0.war': ['org.apache.nifi.web.util.ObjectMapperResolver'],
                    'nifi-standard-content-viewer-2.12.0.war': ['org.apache.nifi.web.controller.StandardContentViewerController'],
                    'nifi-update-attribute-ui-2.12.0.war': ['org.apache.nifi.update.attributes.mapper.ObjectMapperResolver'],
                }.get(Path(ctx['war']).name, [])
                for consumer in consumers:
                    if not (war/'WEB-INF/classes'/Path(consumer.replace('.','/')+'.class')).is_file():
                        raise ValueError('required actual WAR consumer missing: '+consumer)
                cmd=[JAVA,*OPTIONS,'-cp',str(classes)+os.pathsep+cp,'JettyWarProbe',tree,parents,ctx['id'],war,family,version,defining,'false',*consumers]
                stdout,_=run(cmd,variant+'-war-'+str(i))
                if 'jetty-war-roundtrip\t' not in stdout:raise ValueError('missing actual Jetty result')
                for consumer in consumers:
                    if 'consumer-initialized\t'+consumer+'\t' not in stdout:raise ValueError('missing actual WAR consumer initialization')
                    if consumer.endswith('.ObjectMapperResolver') and 'actual-resolver-read\t'+consumer+'\tPASS' not in stdout:raise ValueError('missing actual resolver behavior')
                report.setdefault('observed',[]).append({'variant':variant,'context':ctx,'defining':defining,'changes':changes,'stdout':stdout})
                if variant=='fixed' and ctx['id']=='nifi-jolt-nar':
                    negative=list(cmd);negative[-(len(consumers)+1)]='true'
                    _,stderr=run(negative,'parent-first-negative',expected=1)
                    if 'Jetty Jackson origin mismatch' not in stderr:raise ValueError('parent priority negative failed for unrelated reason')
        if len(report.get('observed',[])) != 10:raise ValueError('incomplete old/fixed WAR coverage')
        report['sources_after']={k:q.file_sha(Path(k)) for k in before}
        if before!=report['sources_after']:raise ValueError('original input/source drift')
        report['status']='bounded-Jetty-WAR-component-controls-passed-not-server-acceptance'
    except Exception as error:
        report.update(status='blocked-Jetty-WAR-component',error=type(error).__name__+': '+str(error));raise
    finally:save()


if __name__=='__main__':main()
