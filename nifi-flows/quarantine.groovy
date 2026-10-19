import groovy.json.JsonOutput
import java.time.Instant
import org.apache.nifi.processor.io.InputStreamCallback
import org.apache.nifi.processor.io.OutputStreamCallback

def flow = session.get()
if (!flow) return
try {
    def bytes = new ByteArrayOutputStream()
    session.read(flow, { input -> input.transferTo(bytes) } as InputStreamCallback)
    def error = [recorded_at:Instant.now().toString(), kafka_key:flow.getAttribute('kafka.key'),
        event_id:flow.getAttribute('cnc.event_id'), raw_record:flow.getAttribute('cnc.raw'),
        content:bytes.toString('UTF-8'), validation_error:flow.getAttribute('cnc.validation.error'),
        record_error:flow.getAttribute('record.error.message'), http_status:flow.getAttribute('invokehttp.status.code'),
        retry_count:flow.getAttribute('flowfile.retries'), meaning:'Rejected laboratory record; never risk zero']
    byte[] output = JsonOutput.toJson(error).getBytes('UTF-8')
    flow = session.write(flow, { stream -> stream.write(output) } as OutputStreamCallback)
    flow = session.putAttribute(flow,'filename','rejected-'+flow.getAttribute('uuid')+'.json')
    session.transfer(flow,REL_SUCCESS)
} catch (Exception error) {
    session.transfer(flow,REL_FAILURE)
}
