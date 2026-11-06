import java.util.Map;
import io.opentelemetry.sdk.autoconfigure.spi.internal.DefaultConfigProperties;
/** A benign, actual SDK consumer of the ConfigUtil ABI that the narrow swap lost. */
public class ConfigPropertiesProbe {
    public static void main(String[] args) {
        var properties=DefaultConfigProperties.createFromMap(Map.of(
            "cnc.qualification", "local", "cnc.count", "7", "cnc.enabled", "true"));
        if(!"local".equals(properties.getString("cnc.qualification"))
            || properties.getInt("cnc.count")!=7 || !properties.getBoolean("cnc.enabled"))
            throw new AssertionError("SDK configuration conversion changed");
        System.out.println("actual-sdk-configutil-consumer=pass");
    }
}
