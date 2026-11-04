"""Strict offline Maven subset for the inspected RabbitMQ/Netty published POMs.

No build/plugin/profile execution, network, version ranges, snapshots or conflict
mediation. Test/provided/optional paths are recorded, not treated as runtime jars.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from verify import NS, require, sha


def model_namespace(root):
    require(root.tag == '{'+NS['m']+'}project', 'unsupported Maven POM namespace')
    def visit(node):
        require(isinstance(node.tag, str) and node.tag.startswith('{'+NS['m']+'}'),
                'unsupported Maven model namespace')
        # Build/plugin configuration is never executed or used for runtime
        # resolution. Its embedded XML need not use the Maven model namespace.
        if node.tag.rsplit('}', 1)[-1] in ('build', 'reporting', 'reports'):
            return
        for child in node:
            visit(child)
    visit(root)

class Closure:
    def __init__(self, cache, pins):
        self.cache=Path(cache)
        self.pins={p['file']:p for p in pins}
        require(len(self.pins)==len(pins), 'duplicate pin name')
        self.models={}; self.decisions=[]; self.profiles=[]
    def model(self, coordinate, stack=()):
        if coordinate in self.models:return self.models[coordinate]
        require(coordinate not in stack, 'POM inheritance/BOM cycle')
        g,a,v=coordinate.split(':');name=f'{a}-{v}.pom'
        require(name in self.pins and self.pins[name].get('coordinate')==coordinate, 'unpinned POM '+coordinate)
        data=(self.cache/name).read_bytes()
        require(sha(data)==self.pins[name].get('sha256'), 'POM integrity '+coordinate)
        root=ET.fromstring(data)
        model_namespace(root)
        def text(n,k,default=None):return n.findtext('m:'+k,default,NS)
        parent=root.find('m:parent',NS)
        pm={'props':{},'management':{},'deps':[]}
        if parent is not None:
            pc=':'.join(text(parent,k) for k in ['groupId','artifactId','version'])
            require('${' not in pc, 'unsupported property parent')
            pm=self.model(pc,stack+(coordinate,))
        props=pm['props']|{x.tag.split('}')[-1]:x.text or '' for x in root.findall('m:properties/*',NS)}
        props.update({'project.groupId':g,'pom.groupId':g,'project.artifactId':a,'project.version':v,'pom.version':v})
        def expand(s):
            require(s is not None, 'missing POM value in '+coordinate)
            for _ in range(20):
                if '${' not in s:return s
                new=re.sub(r'\$\{([^}]+)\}',lambda m:props.get(m[1],m[0]),s)
                if new==s:break
                s=new
            raise ValueError('unresolved POM property '+s+' in '+coordinate)
        for field, expected in (('groupId',g), ('artifactId',a), ('version',v)):
            inherited = text(parent,field) if parent is not None and field != 'artifactId' else None
            require(expand(text(root,field,inherited)) == expected, 'POM coordinate mismatch '+coordinate)
        management=dict(pm['management'])
        def raw(n):
            allowed={'groupId','artifactId','version','scope','optional','type','classifier','exclusions'}
            require(all(x.tag.split('}')[-1] in allowed for x in n), 'unsupported dependency element')
            d={k:text(n,k) for k in allowed-{'exclusions'} if text(n,k) is not None}
            d['exclusions']=[(text(x,'groupId'),text(x,'artifactId')) for x in n.findall('m:exclusions/m:exclusion',NS)]
            return d
        def key(d):return (expand(d['groupId']),expand(d['artifactId']),d.get('type','jar'),d.get('classifier',''))
        # Imported BOMs first, local management overrides imported/inherited entries.
        managed=[raw(n) for n in root.findall('m:dependencyManagement/m:dependencies/m:dependency',NS)]
        for d in managed:
            if d.get('scope')=='import':
                require(d.get('type')=='pom','non-POM BOM')
                bc=':'.join(expand(d[k]) for k in ['groupId','artifactId','version'])
                bm=self.model(bc,stack+(coordinate,))
                for k,val in bm['management'].items():management.setdefault(k,val)
        for d in managed:
            if d.get('scope')!='import':management[key(d)]=d
        deps={key(d):dict(d) for d in pm['deps']}
        for n in root.findall('m:dependencies/m:dependency',NS):
            d=raw(n);k=key(d);md=management.get(k,{})
            # Managed scope/optionality is significant: Netty's Mockito/Gson are tests.
            effective=md|d
            effective['exclusions']=md.get('exclusions',[])+d['exclusions']
            deps[k]=effective
        profile_props=set()
        for profile in root.findall('m:profiles/m:profile',NS):
            require(not profile.findall('m:dependencies/*',NS) and not profile.findall('m:dependencyManagement/*',NS), 'unsupported profile dependency shape')
            profile_props.update(x.tag.split('}')[-1] for x in profile.findall('m:properties/*',NS))
            self.profiles.append({'pom':coordinate,'id':text(profile,'id'),'handling':'no dependency/dependencyManagement changes; required selectors must be profile-independent'})
        # Also inherit profile property names, so children cannot silently use them.
        profile_props.update(pm.get('profile_props',set()))
        resolved=[]
        for d in deps.values():
            scope=d.get('scope','compile');optional=d.get('optional','false')
            require(scope in ('compile','runtime','provided','test','system'), 'unsupported scope '+scope)
            require(scope!='system', 'system dependency forbidden')
            if scope not in ('compile','runtime') or optional=='true':
                self.decisions.append({'pom':coordinate,'raw':d,'disposition':'excluded-'+('optional' if optional=='true' else scope)})
                continue
            require(optional=='false','unsupported optional flag')
            required={k:d.get(k,default) for k,default in [('groupId',None),('artifactId',None),('version',None),('type','jar'),('classifier','')]}
            pending=list(required.values());seen=set()
            while pending:
                value=pending.pop()
                require(value is not None,'missing required dependency version')
                for prop in re.findall(r'\$\{([^}]+)\}',value):
                    require(prop not in profile_props, 'profile-dependent runtime selector '+prop)
                    if prop not in seen:
                        seen.add(prop);pending.append(props.get(prop,''))
            rd={k:expand(val) for k,val in required.items()}
            require(rd['type']=='jar' and rd['classifier']=='','unsupported required artifact type/classifier')
            require(re.fullmatch(r'[0-9][A-Za-z0-9_.-]*',rd['version']) and 'SNAPSHOT' not in rd['version'],'non-exact version')
            rd['scope']=scope
            rd['exclusions']=[(expand(x),expand(y)) for x,y in d['exclusions']]
            resolved.append(rd)
        result={'props':props,'management':management,'deps':list(deps.values()),'required':resolved,'profile_props':profile_props}
        self.models[coordinate]=result
        return result
    def resolve(self, root):
        jars={};visited=set();edges=[]
        def visit(coord,excluded=frozenset()):
            if (coord,excluded) in visited:return
            visited.add((coord,excluded));g,a,v=coord.split(':')
            if (g,a) in excluded or (g,'*') in excluded or ('*','*') in excluded:return
            ga=g+':'+a
            require(ga not in jars or jars[ga]==v, 'version conflict requires review '+ga)
            jars[ga]=v
            model=self.model(coord)
            for d in model['required']:
                target=':'.join(d[k] for k in ['groupId','artifactId','version'])
                skip=(d['groupId'],d['artifactId']) in excluded
                edges.append({'from':coord,'to':target,'scope':d['scope'],'excluded_by_path':skip,'additional_exclusions':d['exclusions']})
                visit(target,excluded|frozenset(d['exclusions']))
        visit(root)
        coordinates=sorted(g+':'+v for g,v in jars.items())
        for coord in coordinates:
            _,a,v=coord.split(':');name=f'{a}-{v}.jar'
            require(name in self.pins and self.pins[name]['coordinate']==coord, 'unpinned required JAR '+coord)
        return {'root':root,'required_coordinates':coordinates,'edges':edges,'excluded_dependencies':self.decisions,'profiles':self.profiles,'poms':sorted(self.models)}
