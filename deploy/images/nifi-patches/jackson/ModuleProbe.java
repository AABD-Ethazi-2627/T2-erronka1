import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.fasterxml.jackson.dataformat.csv.CsvMapper;
import com.fasterxml.jackson.dataformat.csv.CsvSchema;
import java.time.LocalDate;
import java.util.*;
/** Actual stock 2.22.2 module bytes against old/fixed 2.22 core/databind. */
public class ModuleProbe {
    public static void main(String[] args) throws Exception {
        String core=com.fasterxml.jackson.core.json.PackageVersion.VERSION.toString();
        String databind=com.fasterxml.jackson.databind.cfg.PackageVersion.VERSION.toString();
        if(!core.equals(args[0]) || !databind.equals(args[0])) throw new AssertionError("loaded Jackson version");
        ObjectMapper m = new ObjectMapper().registerModule(new JavaTimeModule());
        LocalDate d=LocalDate.of(2026,11,4);
        if(!d.equals(m.readValue(m.writeValueAsString(d),LocalDate.class))) throw new AssertionError("JSR310");
        CsvMapper csv=new CsvMapper();
        CsvSchema schema=CsvSchema.builder().addColumn("name").addColumn("count").build().withHeader();
        Map<String,String> row=new LinkedHashMap<>();row.put("name","a,b");row.put("count","7");
        String text=csv.writer(schema).writeValueAsString(row);
        if(!row.equals(csv.readerFor(Map.class).with(schema).readValue(text))) throw new AssertionError("CSV");
        System.out.println("actual-stock-jsr310-and-csv-roundtrips=pass core="+core+" databind="+databind);
    }
}
