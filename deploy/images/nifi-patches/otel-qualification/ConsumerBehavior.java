import java.lang.reflect.*;
import java.util.*;
import com.google.api.gax.tracing.OpenTelemetryMetricsRecorder;
import com.google.cloud.opentelemetry.detection.GCPPlatformDetector;
import com.google.cloud.opentelemetry.detection.OfflineGcpDetector;
import io.grpc.LongCounterMetricInstrument;
import io.grpc.MetricSink;
import io.opentelemetry.api.common.*;
import io.opentelemetry.api.metrics.Meter;
import io.opentelemetry.contrib.gcp.resource.GCPResourceProvider;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.autoconfigure.spi.internal.DefaultConfigProperties;
import io.opentelemetry.sdk.common.CompletableResultCode;
import io.opentelemetry.sdk.metrics.*;
import io.opentelemetry.sdk.metrics.data.*;
import io.opentelemetry.sdk.metrics.export.*;
import io.opentelemetry.sdk.resources.Resource;

/** Real consumer methods with SDK data capture and deterministic offline inputs. */
public class ConsumerBehavior {
    static final class Capture implements MetricReader {
        CollectionRegistration registration;
        public void register(CollectionRegistration r) { registration=r; }
        public AggregationTemporality getAggregationTemporality(InstrumentType type) { return AggregationTemporality.CUMULATIVE; }
        public CompletableResultCode forceFlush() { return CompletableResultCode.ofSuccess(); }
        public CompletableResultCode shutdown() { return CompletableResultCode.ofSuccess(); }
    }
    static String attributes(Attributes a) {
        Map<String,String> m=new TreeMap<>();a.forEach((k,v)->m.put(k.getKey(),v.toString()));return m.toString();
    }
    static void result(String name,String value) { System.out.println("behavior\t"+name+"\tPASS\t"+value); }
    public static void main(String[] args) throws Exception {
        Capture capture=new Capture();
        try(SdkMeterProvider meters=SdkMeterProvider.builder().registerMetricReader(capture).build();
            OpenTelemetrySdk sdk=OpenTelemetrySdk.builder().setMeterProvider(meters).build()) {
            OpenTelemetryMetricsRecorder recorder=new OpenTelemetryMetricsRecorder(sdk,"cnc.fixture");
            var labels=Map.of("sensor","fixture");
            recorder.recordAttemptLatency(3.5,labels);recorder.recordOperationLatency(7.0,labels);
            recorder.recordAttemptCount(2,labels);recorder.recordOperationCount(1,labels);
            Class<?> sinkType=Class.forName("io.grpc.opentelemetry.OpenTelemetryMetricSink");
            Constructor<?> sinkConstructor=sinkType.getDeclaredConstructor(Meter.class,Map.class,boolean.class,List.class);
            sinkConstructor.setAccessible(true);
            MetricSink sink=(MetricSink)sinkConstructor.newInstance(sdk.getMeter("cnc.grpc"),Map.of(),false,List.of("detail"));
            var instrument=new LongCounterMetricInstrument(0,"cnc.grpc.count","fixture counter","1",List.of("sensor"),List.of("detail"),true);
            sink.updateMeasures(List.of(instrument));sink.addLongCounter(instrument,5,List.of("fixture"),List.of("local"));
            Map<String,String> gax=new TreeMap<>();String grpc=null;
            for(MetricData metric:capture.registration.collectAllMetrics()) {
                if(metric.getType()==MetricDataType.LONG_SUM) {
                    var point=metric.getLongSumData().getPoints().iterator().next();
                    String value=point.getValue()+":"+attributes(point.getAttributes());
                    if(metric.getName().equals("cnc.grpc.count")) {
                        if(point.getValue()!=5 || !"fixture".equals(point.getAttributes().get(AttributeKey.stringKey("sensor")))
                           || !"local".equals(point.getAttributes().get(AttributeKey.stringKey("detail"))))throw new AssertionError("gRPC recorded data");
                        grpc=value;
                    } else gax.put(metric.getName(),value);
                } else if(metric.getType()==MetricDataType.HISTOGRAM) {
                    var point=metric.getHistogramData().getPoints().iterator().next();
                    if(point.getCount()!=1)throw new AssertionError("GAX histogram count");
                    gax.put(metric.getName(),point.getSum()+":"+attributes(point.getAttributes()));
                }
            }
            if(!gax.equals(Map.of("cnc.fixture/attempt_count","2:{sensor=fixture}","cnc.fixture/operation_count","1:{sensor=fixture}",
                "cnc.fixture/attempt_latency","3.5:{sensor=fixture}","cnc.fixture/operation_latency","7.0:{sensor=fixture}")))
                throw new AssertionError("actual GAX output "+gax);
            if(grpc==null)throw new AssertionError("missing actual gRPC output");
            result("gax-metrics",gax.toString());result("grpc-metrics",grpc);
            Class<?> translator=Class.forName("com.google.cloud.opentelemetry.metric.MetricTranslator");
            Method map=translator.getDeclaredMethod("mapMetric",Attributes.class,String.class);map.setAccessible(true);
            com.google.api.Metric metric=(com.google.api.Metric)map.invoke(null,Attributes.builder().put("sensor","fixture").put("count",7L).build(),"custom.googleapis.com/cnc");
            if(!metric.getLabelsMap().equals(Map.of("sensor","fixture","count","7")))throw new AssertionError("actual translator labels");
            result("metric-translator",metric.getType()+":"+new TreeMap<>(metric.getLabelsMap()));
        }
        OfflineGcpDetector detector=new OfflineGcpDetector();
        Constructor<GCPResourceProvider> constructor=GCPResourceProvider.class.getDeclaredConstructor(GCPPlatformDetector.class);
        constructor.setAccessible(true);GCPResourceProvider provider=constructor.newInstance(detector);
        Attributes actual=provider.getAttributes();
        String value=attributes(actual);
        if(!value.equals("{cloud.account.id=fixture-project, cloud.availability_zone=fixture-zone, cloud.platform=gcp_compute_engine, cloud.provider=gcp, cloud.region=fixture-region, host.id=fixture-1}"))
            throw new AssertionError("actual resource mapping "+value);
        var config=DefaultConfigProperties.createFromMap(Map.of());
        if(!provider.shouldApply(config,Resource.empty()) || !provider.createResource(config).getAttributes().equals(actual) || detector.calls!=2)
            throw new AssertionError("actual resource provider calls");
        result("gcp-resource-getAttributes",value);
    }
}
