package com.google.cloud.opentelemetry.detection;

import java.util.Map;

/** Benign local detector stub; production detector/resource JARs stay untouched. */
public final class OfflineGcpDetector extends GCPPlatformDetector {
    public int calls;
    public OfflineGcpDetector() {
        super(new GCPMetadataConfig("http://127.0.0.1:1"), key -> null);
    }
    @Override public DetectedPlatform detectPlatform() {
        calls++;
        return new DetectedPlatform() {
            public SupportedPlatform getSupportedPlatform() { return SupportedPlatform.GOOGLE_COMPUTE_ENGINE; }
            public String getProjectId() { return "fixture-project"; }
            public Map<String,String> getAttributes() {
                return Map.of(AttributeKeys.GCE_INSTANCE_ID,"fixture-1",
                    AttributeKeys.GCE_AVAILABILITY_ZONE,"fixture-zone",
                    AttributeKeys.GCE_CLOUD_REGION,"fixture-region");
            }
        };
    }
}
