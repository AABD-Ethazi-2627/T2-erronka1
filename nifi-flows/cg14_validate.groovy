// CG14 — validación de ingesta (propuesta v0.1.0, NiFi 1.25.0, motor Groovy).
//
// Única fuente de verdad del script: este fichero. El flow JSON lo incrusta
// y tests/test_cg14_nifi_flow.py exige que ambos sean idénticos.
// Reglas = docs/CG14_VALIDATION_CONTRACT.md + cg14_validation/validator.py.
//
// Entrada: contenido = 1 línea CSV (timestamp + 13 columnas).
// Atributos de entrada: kafka.topic/partition/offset, cg14.source.kind,
//   cg14.max.line.bytes, cg14.max.field.chars, cg14.schema.version.
// Salida REL_SUCCESS con contenido JSON:
//   válido   -> evento normalizado SIN etiquetas + cg14.valid=true
//   rechazado-> sobre de error auditable + cg14.valid=false/cg14.code/cg14.field
// Salida REL_FAILURE solo ante error del motor (no de validación).

import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Instant
import org.apache.nifi.processor.io.InputStreamCallback
import org.apache.nifi.processor.io.OutputStreamCallback

def flowFile = session.get()
if (flowFile == null) { return }

def fail(reason, field, raw, attrs) {
    def now = Instant.now().toString()
    def envelope = '{"valid":false'
        + ',"code":' + jsonStr(reason)
        + ',"field":' + jsonStr(field)
        + ',"message":' + jsonStr(msgFor(reason, field))
        + ',"event_id":null'
        + ',"source":{"kind":' + jsonStr(attrs['kind'])
        + ',"uri":' + jsonStr(attrs['uri'])
        + ',"record_ref":' + jsonStr(attrs['ref'])
        + ',"raw_record":' + jsonStr(raw)
        + '},"reject_time":' + jsonStr(now)
        + ',"original":' + jsonStr(raw) + '}'
    return [envelope, ['cg14.valid': 'false', 'cg14.code': reason,
        'cg14.field': field ?: '', 'cg14.event.id': '',
        'cg14.warning': '', 'machine.id': '', 'cg14.reject.time': now]]
}

def jsonStr(s) {
    if (s == null) { return 'null' }
    def t = s.replace('\\', '\\\\').replace('"', '\\"')
        .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return '"' + t + '"'
}

def msgFor(code, field) {
    switch (code) {
        case 'MESSAGE_TOO_LARGE': return 'line or field exceeds configured budget'
        case 'MALFORMED_CSV': return 'expected timestamp plus 13 CSV fields'
        case 'HEADER_ROW': return 'header row received as data'
        case 'INVALID_TIMESTAMP': return 'expected UTC ISO-8601 ending in Z'
        case 'INVALID_MACHINE_ID': return 'expected CNC-000 format'
        case 'INVALID_MACHINE_TYPE': return 'expected H, M or L'
        case 'INVALID_NUMERIC': return 'CSV contains a non-numeric value'
        case 'NON_FINITE_NUMERIC': return 'NaN and infinity are forbidden'
        case 'NEGATIVE_PHYSICAL_VALUE': return 'physical measurements cannot be negative'
        case 'INVALID_LABEL': return 'CSV label columns must be 0 or 1'
        default: return 'rejected by CG14 validation'
    }
}

def splitCsv(line) {
    def fields = []
    def cur = new StringBuilder()
    def inQuotes = false
    for (int i = 0; i < line.length(); i++) {
        def c = line.charAt(i)
        if (inQuotes) {
            if (c == '"') {
                if (i + 1 < line.length() && line.charAt(i + 1) == '"') { cur.append('"'); i++ }
                else { inQuotes = false }
            } else { cur.append(c) }
        } else if (c == '"') { inQuotes = true }
        else if (c == ',') { fields.add(cur.toString()); cur = new StringBuilder() }
        else { cur.append(c) }
    }
    if (inQuotes) { return null }
    fields.add(cur.toString())
    return fields
}

try {
    def kind = flowFile.getAttribute('cg14.source.kind') ?: 'nifi-cg14'
    def uri = flowFile.getAttribute('cg14.source.uri') ?: 'kafka://unknown'
    def ref = flowFile.getAttribute('cg14.record.ref') ?: 'nifi:unknown'
    def schema = flowFile.getAttribute('cg14.schema.version') ?: '0.1.0'
    def maxLine = (flowFile.getAttribute('cg14.max.line.bytes') ?: '8192') as long
    def maxField = (flowFile.getAttribute('cg14.max.field.chars') ?: '512') as int
    def attrs = ['kind': kind, 'uri': uri, 'ref': ref]

    def rawBytes = session.read(flowFile, { ins -> ins.bytes } as InputStreamCallback)
    if (rawBytes.length > maxLine) {
        def r = fail('MESSAGE_TOO_LARGE', '', '', attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    def raw = new String(rawBytes, StandardCharsets.UTF_8).replaceAll(/[\r\n]+$/, '')
    def values = splitCsv(raw)
    if (values == null || values.size() != 14) {
        def first = (values && values.size() > 0) ? values[0].toLowerCase() : ''
        def code = (first == 'timestamp' || first == 'machine_id') ? 'HEADER_ROW' : 'MALFORMED_CSV'
        def r = fail(code, '', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    def names = ['timestamp', 'machine_id', 'machine_type', 'air_temp_K', 'process_temp_K',
        'rpm', 'torque_Nm', 'tool_wear_min', 'machine_failure', 'failure_TWF',
        'failure_HDF', 'failure_PWF', 'failure_OSF', 'failure_RNF']
    def row = [:]
    names.eachWithIndex { n, i -> row[n] = values[i] }
    if (row['timestamp'].trim().toLowerCase() == 'timestamp'
        || row['machine_id'].trim().toLowerCase() == 'machine_id'
        || row['machine_type'].trim().toLowerCase() == 'machine_type') {
        def r = fail('HEADER_ROW', '', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    def over = names.find { row[it].length() > maxField }
    if (over) {
        def r = fail('MESSAGE_TOO_LARGE', over, raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    if (!(row['timestamp'] ==~ /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$/)) {
        def r = fail('INVALID_TIMESTAMP', 'timestamp', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    try { Instant.parse(row['timestamp']) }
    catch (Exception e) {
        def r = fail('INVALID_TIMESTAMP', 'timestamp', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    if (!(row['machine_id'] ==~ /^CNC-[0-9]{3}$/)) {
        def r = fail('INVALID_MACHINE_ID', 'machine_id', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    if (!(row['machine_type'] in ['H', 'M', 'L'])) {
        def r = fail('INVALID_MACHINE_TYPE', 'machine_type', raw, attrs)
        flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
        flowFile = session.putAllAttributes(flowFile, r[1])
        session.transfer(flowFile, REL_SUCCESS)
        return
    }
    def sensors = ['air_temp_K', 'process_temp_K', 'rpm', 'torque_Nm', 'tool_wear_min']
    def nonNeg = ['rpm', 'torque_Nm', 'tool_wear_min'] as Set
    def nums = [:]
    for (s in sensors) {
        double v
        try { v = Double.parseDouble(row[s]) }
        catch (NumberFormatException e) {
            def r = fail('INVALID_NUMERIC', s, raw, attrs)
            flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
            flowFile = session.putAllAttributes(flowFile, r[1])
            session.transfer(flowFile, REL_SUCCESS)
            return
        }
        if (Double.isNaN(v) || Double.isInfinite(v)) {
            def r = fail('NON_FINITE_NUMERIC', s, raw, attrs)
            flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
            flowFile = session.putAllAttributes(flowFile, r[1])
            session.transfer(flowFile, REL_SUCCESS)
            return
        }
        if (v < 0 && nonNeg.contains(s)) {
            def r = fail('NEGATIVE_PHYSICAL_VALUE', s, raw, attrs)
            flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
            flowFile = session.putAllAttributes(flowFile, r[1])
            session.transfer(flowFile, REL_SUCCESS)
            return
        }
        nums[s] = v
    }
    def labels = ['machine_failure', 'failure_TWF', 'failure_HDF', 'failure_PWF', 'failure_OSF', 'failure_RNF']
    for (l in labels) {
        // trim: paridad con int() de Python, que ignora espacios alrededor
        if (!(row[l].trim() == '0' || row[l].trim() == '1')) {
            def r = fail('INVALID_LABEL', l, raw, attrs)
            flowFile = session.write(flowFile, { out -> out.write(r[0].getBytes('UTF-8')) } as OutputStreamCallback)
            flowFile = session.putAllAttributes(flowFile, r[1])
            session.transfer(flowFile, REL_SUCCESS)
            return
        }
    }
    def active = labels.find { row[it].trim() == '1' }
    def warning = active ? 'TRAINING_LABEL_STRIPPED' : ''

    def digest = MessageDigest.getInstance('SHA-256')
    def eventId = digest.digest(('cnc.telemetry.v' + schema + '\n' + kind + '\n' + raw).getBytes(StandardCharsets.UTF_8)).encodeHex().toString()
    def event = '{"event_id":' + jsonStr(eventId)
        + ',"machine_id":' + jsonStr(row['machine_id'])
        + ',"timestamp":' + jsonStr(row['timestamp'])
        + ',"schema_version":' + jsonStr(schema)
        + ',"quality_flag":"OK"'
        + ',"source":{"kind":' + jsonStr(kind)
        + ',"uri":' + jsonStr(uri)
        + ',"record_ref":' + jsonStr(ref)
        + ',"raw_record":' + jsonStr(raw) + '}'
        + ',"machine_type":' + jsonStr(row['machine_type'])
        + sensors.collect { ',"' + it + '":' + nums[it] }.join('')
        + '}'
    flowFile = session.write(flowFile, { out -> out.write(event.getBytes('UTF-8')) } as OutputStreamCallback)
    flowFile = session.putAllAttributes(flowFile, ['cg14.valid': 'true', 'cg14.code': '',
        'cg14.field': '', 'cg14.event.id': eventId, 'cg14.warning': warning,
        'machine.id': row['machine_id'], 'cg14.reject.time': ''])
    session.transfer(flowFile, REL_SUCCESS)
} catch (Exception e) {
    flowFile = session.putAttribute(flowFile, 'cg14.engine.error', e.toString())
    session.transfer(flowFile, REL_FAILURE)
}
