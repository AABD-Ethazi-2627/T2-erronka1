// NiFi validates only. No model, imputer, scaling or probability logic here.
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Instant
import org.apache.nifi.processor.io.InputStreamCallback
import org.apache.nifi.processor.io.OutputStreamCallback

def flow = session.get()
if (!flow) return
try {
    def rawBytes = new ByteArrayOutputStream()
    session.read(flow, { input -> input.transferTo(rawBytes) } as InputStreamCallback)
    def record = new JsonSlurper().parseText(rawBytes.toString('UTF-8'))
    if (record instanceof List) {
        if (record.size() != 1) throw new IllegalArgumentException('Expected one record')
        record = record[0]
    }
    def raw = flow.getAttribute('cnc.raw')
    if (!raw) throw new IllegalArgumentException('Missing original CSV')
    raw = raw.strip()
    def fields = raw.split(',', -1)
    if (fields.length != 14) throw new IllegalArgumentException('CSV width')
    if (!(fields[0] ==~ /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z/)) throw new IllegalArgumentException('UTC required')
    Instant.parse(fields[0])
    if (!(fields[1] ==~ /CNC-\d{3}/) || !(fields[2] in ['H','M','L'])) throw new IllegalArgumentException('identity')
    def names = ['air_temp_K','process_temp_K','rpm','torque_Nm','tool_wear_min']
    def event = [machine_id:fields[1], timestamp:fields[0], machine_type:fields[2], schema_version:'0.1.0', quality_flag:'OK']
    names.eachWithIndex { name, i ->
        if (!(record[name] instanceof Number)) throw new IllegalArgumentException('Numeric schema required')
        double value = record[name].doubleValue()
        if (!Double.isFinite(value) || (i<2 ? value<=0 : value<0)) throw new IllegalArgumentException('sensor domain')
        event[name] = value
    }
    if (!(fields[8..13].every { it in ['0','1'] })) throw new IllegalArgumentException('label format')
    def key = flow.getAttribute('kafka.key')
    if (!key) throw new IllegalArgumentException('Missing stable source record key')
    event.event_id = MessageDigest.getInstance('SHA-256').digest(key.getBytes(StandardCharsets.UTF_8)).encodeHex().toString()
    event.source = [kind:(flow.getAttribute('kafka.topic') == 'cnc-sensors-smb-v1' ? 'smb_csv' : 'lab_fixture'), uri:'kafka://kafka:9092/'+flow.getAttribute('kafka.topic'), record_ref:key]
    def content = JsonOutput.toJson(event).getBytes(StandardCharsets.UTF_8)
    flow = session.write(flow, { output -> output.write(content) } as OutputStreamCallback)
    flow = session.putAllAttributes(flow, ['mime.type':'application/json', 'cnc.event_id':event.event_id, 'filename':event.event_id+'.json'])
    session.transfer(flow, REL_SUCCESS)
} catch (Exception error) {
    flow = session.putAttribute(flow, 'cnc.validation.error', error.getClass().getSimpleName())
    session.transfer(flow, REL_FAILURE)
}
