/** Executes the existing bounded library controls through the installed AWS NAR. */
public final class LibraryExercise {
    public static void main(String[] args) throws Exception {
        LibraryProbe.main(new String[] {"guava", "fixed"});
        LibraryProbe.main(new String[] {"lz4", "fixed"});
        LibraryProbe.main(new String[] {"snappy", "fixed"});
    }
}
