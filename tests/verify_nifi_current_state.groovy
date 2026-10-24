// Executes the production Groovy normalizer with in-memory session callbacks.
// This is a script-level test, not a claim of a live NiFi-to-Kafka integration.
import groovy.json.JsonOutput
import groovy.json.JsonSlurper

class FixtureFlow {
    Map attributes
    byte[] body
    String getAttribute(String name) { attributes[name] }
}
class FixtureSession {
    FixtureFlow flow
    String relation
    def get() { flow }
    def read(f, callback) { callback.process(new ByteArrayInputStream(f.body)) }
    def write(f, callback) {
        def output = new ByteArrayOutputStream()
        callback.process(output)
        f.body = output.toByteArray()
        f
    }
    def putAllAttributes(f, values) { f.attributes.putAll(values); f }
    def putAttribute(f, key, value) { f.attributes[key] = value; f }
    def transfer(f, rel) { relation = rel }
}

def loader = new GroovyClassLoader(this.class.classLoader)
loader.parseClass('''package org.apache.nifi.processor.io
interface InputStreamCallback { void process(java.io.InputStream input) }
interface OutputStreamCallback { void process(java.io.OutputStream output) }
''')
def execute = { String labels ->
    def raw = '2026-10-20T10:00:00Z,CNC-001,M,300.0,310.0,1500,40.0,100,' + labels
    def record = [air_temp_K:300.0, process_temp_K:310.0, rpm:1500,
                  torque_Nm:40.0, tool_wear_min:100, machine_failure:1,
                  failure_TWF:1, failure_HDF:1, failure_PWF:1, failure_OSF:1, failure_RNF:1]
    def flow = new FixtureFlow(attributes:['cnc.raw':raw, 'kafka.key':'scope-fixture:row-1',
                                           'kafka.topic':'cnc-sensors-lab-v1'],
                               body:JsonOutput.toJson(record).getBytes('UTF-8'))
    def session = new FixtureSession(flow:flow)
    def binding = new Binding([session:session, REL_SUCCESS:'success', REL_FAILURE:'failure'])
    new GroovyShell(loader,binding).evaluate(new File('nifi-flows/normalize_csv.groovy'))
    assert session.relation == 'success'
    new JsonSlurper().parseText(new String(flow.body,'UTF-8'))
}
def a = execute('0,0,0,0,0,0')
def b = execute('1,1,1,1,1,1')
assert a == b : 'Changing labels must never change the request'
assert !a.source.containsKey('raw_record')
assert !a.keySet().any { it == 'machine_failure' || it.startsWith('failure_') }
assert a.machine_type == 'M'
if (args.length) {
    def destination = new File(args[0])
    assert !destination.exists()
    destination.parentFile.mkdirs()
    destination.text = JsonOutput.prettyPrint(JsonOutput.toJson(a)) + '\n'
}
println 'PASS: production normalizer strips labels and raw CSV; label changes leave request identical.'
