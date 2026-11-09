import java.util.*;
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.metrics.SdkMeterProvider;
import io.opentelemetry.sdk.logs.SdkLoggerProvider;

/** Benign component controls; no exporters, global registration or servers. */
public class OtelExercise {
    static final TextMapGetter<Map<String,String>> GETTER = new TextMapGetter<>() {
        public Iterable<String> keys(Map<String,String> carrier) { return carrier.keySet(); }
        public String get(Map<String,String> carrier, String key) { return carrier.get(key); }
    };
    public static void main(String[] args) throws Exception {
        OpenTelemetrySdk sdk=OpenTelemetrySdk.builder()
            .setTracerProvider(SdkTracerProvider.builder().build())
            .setMeterProvider(SdkMeterProvider.builder().build())
            .setLoggerProvider(SdkLoggerProvider.builder().build()).build();
        try {
            OpenTelemetry api=sdk;
            Span span=api.getTracer("cnc-qualification").spanBuilder("bounded-local").startSpan();
            try (Scope scope=span.makeCurrent()) {
                if (!Span.current().getSpanContext().equals(span.getSpanContext()))
                    throw new AssertionError("SDK context did not propagate");
                Context baggage=Baggage.builder().put("qualification", "local").build().storeInContext(Context.current());
                if (!"local".equals(Baggage.fromContext(baggage).getEntryValue("qualification")))
                    throw new AssertionError("baggage roundtrip");
                api.getMeter("cnc-qualification").counterBuilder("bounded_count").build().add(1);
                api.getLogsBridge().loggerBuilder("cnc-qualification").build().logRecordBuilder()
                    .setBody("bounded-local-control").emit();
            } finally { span.end(); }
            var propagator=W3CTraceContextPropagator.getInstance();
            Map<String,String> headers=new LinkedHashMap<>();
            headers.put("traceparent", "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01");
            headers.put("tracestate", "cnc=local,other=valid");
            Context extracted=propagator.extract(Context.root(),headers,GETTER);
            var sc=Span.fromContext(extracted).getSpanContext();
            if (!sc.isValid() || !sc.getTraceId().equals("4bf92f3577b34da6a3ce929d0e0e4736")
                || !"local".equals(sc.getTraceState().get("cnc")))
                throw new AssertionError("valid W3C context");
            Map<String,String> injected=new LinkedHashMap<>();
            propagator.inject(extracted,injected,Map::put);
            if (!headers.get("traceparent").equals(injected.get("traceparent")))
                throw new AssertionError("injected traceparent");
            // Bounded compatibility/security-limit controls, not timing/OOM probes.
            headers.put("tracestate", "invalid member");
            if (!Span.fromContext(propagator.extract(Context.root(),headers,GETTER))
                .getSpanContext().getTraceState().isEmpty())
                throw new AssertionError("malformed tracestate accepted");
            StringJoiner tooMany=new StringJoiner(",");
            for(int i=0;i<33;i++)tooMany.add("k"+i+"=v");
            headers.put("tracestate",tooMany.toString());
            int[] members={0};
            Span.fromContext(propagator.extract(Context.root(),headers,GETTER))
                .getSpanContext().getTraceState().forEach((k,v)->members[0]++);
            if(members[0]>32)throw new AssertionError("tracestate member maximum exceeded");
            System.out.println("tracestate-bounded-valid-invalid-overmaximum=pass retained="+members[0]);
            headers.put("traceparent", "invalid");
            if (Span.fromContext(propagator.extract(Context.root(),headers,GETTER)).getSpanContext().isValid())
                throw new AssertionError("malformed traceparent accepted");
            System.out.println("sdk-trace-context-baggage-metrics-logs=pass propagation-valid-invalid=pass");
        } finally { sdk.close(); }
    }
}
