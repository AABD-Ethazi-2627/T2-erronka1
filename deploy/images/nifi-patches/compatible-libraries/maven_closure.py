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
        require(root.find('m:distributionManagement/m:relocation',NS) is None,
                'unsupported Maven distribution relocation')
        def text(n,k,default=None):return n.findtext('m:'+k,default,NS)
        parent=root.find('m:parent',NS)
        pm={'props':{},'management':{},'deps':[]}
        if parent is not None:
            pc=':'.join(text(parent,k) for k in ['groupId','artifactId','version'])
            require('${' not in pc, 'unsupported property parent')
            pm=self.model(pc,stack+(coordinate,))
        props=pm['props']|{x.tag.split('}')[-1]:x.text or '' for x in root.findall('m:properties/*',NS)}
        props.update({'project.groupId':g,'pom.groupId':g,'project.artifactId':a,'project.version':v,'pom.version':v})
        profile_props=set(pm.get('profile_props',set()))
        profile_values={k:set(values) for k,values in pm.get('profile_values',{}).items()}
        for profile in root.findall('m:profiles/m:profile',NS):
            for x in profile.findall('m:properties/*',NS):
                name=x.tag.split('}')[-1];profile_props.add(name)
                profile_values.setdefault(name,set()).add(x.text or '')
        def expand(s, property_values=None):
            property_values=props if property_values is None else property_values
            require(s is not None, 'missing POM value in '+coordinate)
            for _ in range(20):
                if '${' not in s:return s
                new=re.sub(r'\$\{([^}]+)\}',lambda m:property_values.get(m[1],m[0]),s)
                if new==s:break
                s=new
            raise ValueError('unresolved POM property '+s+' in '+coordinate)
        for field, expected in (('groupId',g), ('artifactId',a), ('version',v)):
            inherited = text(parent,field) if parent is not None and field != 'artifactId' else None
            require(expand(text(root,field,inherited)) == expected, 'POM coordinate mismatch '+coordinate)
        management=dict(pm['management'])
        # Inherited dependency-management keys were interpolated in the parent.
        # Refuse a changed child interpolation instead of retaining a stale key.
        for inherited_key, inherited_dependency in management.items():
            require(tuple(expand(inherited_dependency[field]) for field in ('groupId','artifactId'))
                    == inherited_key[:2], 'unsupported inherited management key interpolation')
        def raw(n):
            allowed={'groupId','artifactId','version','scope','optional','type','classifier','exclusions'}
            require(all(x.tag.split('}')[-1] in allowed for x in n), 'unsupported dependency element')
            d={k:text(n,k) for k in allowed-{'exclusions'} if text(n,k) is not None}
            d['exclusions']=[(text(x,'groupId'),text(x,'artifactId')) for x in n.findall('m:exclusions/m:exclusion',NS)]
            return d
        def independent(values):
            pending=list(values);seen=set()
            while pending:
                value=pending.pop()
                require(value is not None,'missing required dependency selector')
                require(value==value.strip(),'unsupported selector whitespace')
                for prop in re.findall(r'\$\{([^}]+)\}',value):
                    require(prop not in profile_props,'profile-dependent runtime selector '+prop)
                    if prop not in seen:
                        seen.add(prop);pending.append(props.get(prop,''))
        def key(d,managed=False):
            values=(d['groupId'],d['artifactId'],d.get('type','jar'),d.get('classifier',''))
            if not managed:independent(values[:2])
            # Optional/native management can contain profile-specific classifier
            # keys. Do not resolve an unused classifier as a runtime dependency.
            # Its GA is marked uncertain below and rejected if actually required.
            result=tuple(expand(value) for value in values[:2])+values[2:]
            require(all(value==value.strip() for value in result),'unsupported selector whitespace')
            return result
        # Imported BOMs first, local management overrides imported/inherited entries.
        managed=[raw(n) for n in root.findall('m:dependencyManagement/m:dependencies/m:dependency',NS)]
        uncertain_management=set(pm.get('uncertain_management',set()))
        def possibilities(value,stack=()):
            match=re.search(r'\$\{([^}]+)\}',value)
            if match is None:
                require(value==value.strip(),'unsupported selector whitespace')
                return {value}
            prop=match[1]
            require(prop not in stack,'cyclic management selector')
            values=profile_values.get(prop,set())|{props.get(prop,'${'+prop+'}')}
            result=set()
            for replacement in values:
                require(replacement!='${'+prop+'}','unresolved management selector '+prop)
                for resolved in possibilities(replacement,stack+(prop,)):
                    result.update(possibilities(value[:match.start()]+resolved+value[match.end():],stack))
                    require(len(result)<=64,'unsupported management selector variant count')
            return result
        for dependency in managed:
            groups=possibilities(dependency['groupId']);artifacts=possibilities(dependency['artifactId'])
            if len(groups)>1 or len(artifacts)>1 or any('${' in dependency.get(field,'') for field in ('type','classifier')):
                uncertain_management.update((group,artifact) for group in groups for artifact in artifacts)
        imports=[d for d in managed if d.get('scope')=='import']
        inherited_imports=pm.get('imports',[])
        require(not (inherited_imports and imports),'unsupported inherited BOM import priority')
        pending=[str(d) for d in inherited_imports];import_props=set()
        while pending:
            for prop in re.findall(r'\$\{([^}]+)\}',pending.pop()):
                if prop not in import_props:
                    import_props.add(prop);pending.append(pm['props'].get(prop,''))
        require(not any(props.get(prop)!=pm['props'].get(prop) for prop in import_props),
                'unsupported inherited BOM property interpolation')
        imported_management={}
        for d in managed:
            key(d,managed=True)
            if d.get('scope')=='import':
                require(d.get('type')=='pom','non-POM BOM')
                independent(d[k] for k in ['groupId','artifactId','version'])
                bc=':'.join(expand(d[k]) for k in ['groupId','artifactId','version'])
                bm=self.model(bc,stack+(coordinate,))
                uncertain_management.update(bm.get('uncertain_management',set()))
                for k,val in bm['management'].items():
                    # Do not interpolate BOM-owned values in the consumer's
                    # property context. This subset refuses such required values.
                    fields=set(val.get('_unsupported_bom_fields',[]))
                    fields.update(name for name,value in val.items()
                                  if not name.startswith('_') and '${' in str(value))
                    if k not in management:
                        management[k]=val|{'_unsupported_bom_fields':sorted(fields)}
                        imported_management[k]=management[k]
        for d in managed:
            if d.get('scope')!='import':management[key(d,managed=True)]=d
        # Parent dependencies already carry their parent's management. Refuse
        # to re-key them in a child while silently retaining that old scope.
        for inherited_dependency in pm['deps']:
            require(tuple(expand(inherited_dependency[field]) for field in ('groupId','artifactId'))
                    == tuple(expand(inherited_dependency[field],pm['props']) for field in ('groupId','artifactId')),
                    'unsupported inherited dependency key interpolation')
        deps={key(d,managed=True):dict(d) for d in pm['deps']}
        local_management=imported_management|{key(d,managed=True):d for d in managed if d.get('scope')!='import'}
        for k,d in deps.items():
            local=local_management.get(k,{})
            if (any(field in local and expand(local[field])!=expand(d.get(field,default))
                    for field,default in (('version',''),('scope','compile'),
                                          ('type','jar'),('classifier',''),('optional','false')))
                    or (local.get('exclusions') and local['exclusions']!=d.get('exclusions',[]))):
                d['_unsupported_inherited_management']=True
        for n in root.findall('m:dependencies/m:dependency',NS):
            d=raw(n);k=key(d,managed=True);md=management.get(k,{})
            # Maven manages scope, but not optionality. Explicit optional=true
            # in the dependency itself still excludes that runtime path.
            effective={field:value for field,value in md.items()
                       if not field.startswith('_') and field!='optional'}|d
            used={field for field in md if field not in d or (field=='exclusions' and not d['exclusions'])}
            effective['_unsupported_bom_fields']=sorted(used & set(md.get('_unsupported_bom_fields',[])))
            effective['_unsupported_exclusion_merge']=bool(md.get('exclusions') and d['exclusions'])
            effective['exclusions']=d['exclusions'] or md.get('exclusions',[])
            deps[k]=effective
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
            if optional!='true':
                # An inherited test/provided path can become required through
                # child management. Do not discard it before rejecting the mark.
                require(not d.get('_unsupported_inherited_management'),
                        'unsupported inherited dependency management override')
                # An ambiguous plain-JAR key can hide a runtime edge as test.
                # A classified test-only artifact is a different Maven key;
                # keep unused native test classifiers out of runtime resolution.
                if d.get('type','jar')=='jar' and not d.get('classifier'):
                    require((expand(d['groupId']),expand(d['artifactId'])) not in uncertain_management,
                            'unsupported management key for required dependency (profile-dependent runtime selector or interpolation)')
            if scope not in ('compile','runtime') or optional=='true':
                self.decisions.append({'pom':coordinate,'raw':d,'disposition':'excluded-'+('optional' if optional=='true' else scope)})
                continue
            require(optional=='false','unsupported optional flag')
            require((expand(d['groupId']),expand(d['artifactId'])) not in uncertain_management,
                    'unsupported management key for required dependency (profile-dependent runtime selector or interpolation)')
            require(not any('${' in d.get(field,'') for field in ('type','classifier')),
                    'unsupported interpolated dependency type/classifier')
            require(not d.get('_unsupported_bom_fields'), 'unsupported interpolated BOM requirement')
            require(not d.get('_unsupported_exclusion_merge'), 'unsupported managed/local exclusion combination')
            required={k:d.get(k,default) for k,default in [('groupId',None),('artifactId',None),('version',None),('type','jar'),('classifier','')]}
            pending=list(required.values())+[value for pair in d['exclusions'] for value in pair];seen=set()
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
            require(all(value==value.strip() for pair in rd['exclusions'] for value in pair),
                    'unsupported selector whitespace')
            resolved.append(rd)
        result={'props':props,'management':management,'deps':list(deps.values()),'required':resolved,'profile_props':profile_props,
                'imports':inherited_imports+imports,'uncertain_management':uncertain_management,
                'profile_values':profile_values}
        self.models[coordinate]=result
        return result
    def resolve(self, root):
        jars={};visited=set();edges=[];contexts={};descendants={}
        def excluded_by(g,a,excluded):
            return any(pair in excluded for pair in ((g,a),(g,'*'),('*',a),('*','*')))
        def reachable(coord,stack=()):
            if coord in descendants:return descendants[coord]
            require(coord not in stack,'runtime dependency cycle unsupported')
            result=set()
            for d in self.model(coord)['required']:
                result.add((d['groupId'],d['artifactId']))
                child=':'.join(d[k] for k in ['groupId','artifactId','version'])
                result.update(reachable(child,stack+(coord,)))
            descendants[coord]=result
            return result
        def visit(coord,excluded=frozenset(),below=frozenset(),ancestry=()):
            require(coord not in ancestry,'runtime dependency cycle unsupported')
            state=(coord,excluded,below)
            if state in visited:return
            visited.add(state);g,a,v=coord.split(':')
            if excluded_by(g,a,excluded):return
            context=(excluded,below)
            if coord in contexts and contexts[coord]!=context:
                previous=contexts[coord][0]|contexts[coord][1]
                current=excluded|below
                require(all(excluded_by(g,a,previous)==excluded_by(g,a,current)
                            for g,a in reachable(coord)),
                        'path-dependent exclusions require real Maven mediation '+coord)
            contexts[coord]=context
            ga=g+':'+a
            require(ga not in jars or jars[ga]==v, 'version conflict requires review '+ga)
            jars[ga]=v
            model=self.model(coord)
            children_excluded=excluded|below
            for d in model['required']:
                target=':'.join(d[k] for k in ['groupId','artifactId','version'])
                skip=excluded_by(d['groupId'],d['artifactId'],children_excluded)
                edges.append({'from':coord,'to':target,'scope':d['scope'],'excluded_by_path':skip,'additional_exclusions':d['exclusions']})
                # An edge's exclusions apply below its target, not to the
                # dependency declaring them (including self and wildcard rules).
                visit(target,children_excluded,frozenset(d['exclusions']),ancestry+(coord,))
        visit(root)
        coordinates=sorted(g+':'+v for g,v in jars.items())
        for coord in coordinates:
            _,a,v=coord.split(':');name=f'{a}-{v}.jar'
            require(name in self.pins and self.pins[name]['coordinate']==coord, 'unpinned required JAR '+coord)
        return {'root':root,'required_coordinates':coordinates,'edges':edges,'excluded_dependencies':self.decisions,'profiles':self.profiles,'poms':sorted(self.models)}
