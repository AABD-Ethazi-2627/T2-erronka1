import java.nio.file.*;
import java.util.*;
import org.apache.parquet.hadoop.*;
import org.apache.parquet.hadoop.metadata.*;
import org.apache.parquet.io.*;
import org.apache.parquet.schema.*;
import shaded.parquet.com.fasterxml.jackson.databind.json.JsonMapper;
public final class ParquetProbe {
  public static void main(String[] args) throws Exception {
    MessageType schema = MessageTypeParser.parseMessageType("message bounded { required int64 id; optional binary label (UTF8); }");
    ParquetMetadata metadata = new ParquetMetadata(new FileMetaData(schema,Map.of("proof","é"),"bounded-local-probe"),List.of());
    JsonMapper mapper = new JsonMapper();
    var compact = mapper.readTree(ParquetMetadata.toJSON(metadata));
    var pretty = mapper.readTree(ParquetMetadata.toPrettyJSON(metadata));
    if (!compact.equals(pretty) || !compact.toString().contains("bounded-local-probe")) throw new AssertionError("actual ParquetMetadata JSON consumer");
    Path path=Path.of(args[0]);
    if (Files.exists(path)) throw new AssertionError("preserve existing output");
    var groups=new org.apache.parquet.example.data.simple.SimpleGroupFactory(schema);
    try (org.apache.parquet.hadoop.ParquetWriter<org.apache.parquet.example.data.Group> w=
        org.apache.parquet.hadoop.example.ExampleParquetWriter.builder(new LocalOutputFile(path))
        .withConf(new org.apache.parquet.conf.PlainParquetConfiguration()).withType(schema)
        .withCompressionCodec(CompressionCodecName.UNCOMPRESSED).withDictionaryEncoding(false)
        .withRowGroupSize(1024*1024).withPageSize(4096).build()) {
      w.write(groups.newGroup().append("id",1L).append("label","é"));
      w.write(groups.newGroup().append("id",2L).append("label","normal"));
      w.write(groups.newGroup().append("id",3L));
    }
    try (ParquetFileReader r=ParquetFileReader.open(new LocalInputFile(path),org.apache.parquet.ParquetReadOptions.builder(new org.apache.parquet.conf.PlainParquetConfiguration()).build())) {
      if (r.getRecordCount()!=3 || !r.getFileMetaData().getSchema().equals(schema)) throw new AssertionError("file footer roundtrip");
      var pages=r.readNextRowGroup();
      var columns=new org.apache.parquet.io.ColumnIOFactory().getColumnIO(schema);
      var reader=columns.getRecordReader(pages,new org.apache.parquet.example.data.simple.convert.GroupRecordConverter(schema));
      for(int i=1;i<=3;i++) {
        var row=reader.read();
        if(row.getLong("id",0)!=i) throw new AssertionError("row id");
        if(i==1 && !row.getString("label",0).equals("é")) throw new AssertionError("unicode row");
        if(i==3 && row.getFieldRepetitionCount("label")!=0) throw new AssertionError("optional null row");
      }
    }
    System.out.println("ParquetMetadata real JSON consumer + three-row UNCOMPRESSED Parquet file/footer read-write=pass size="+Files.size(path)
      +" mapper-source="+JsonMapper.class.getProtectionDomain().getCodeSource().getLocation()
      +" consumer-source="+ParquetMetadata.class.getProtectionDomain().getCodeSource().getLocation());
  }
}
