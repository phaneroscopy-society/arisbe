import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import aminePlatform.engines.prologPlusCG.interpreter.Interpreter;
import aminePlatform.kernel.lexicons.Lexicon;
import aminePlatform.util.cg.CG;

public final class AmineCgifProbe {
  private AmineCgifProbe() {}
  private static String normalized(String value){ return value==null ? "" : value.replaceAll("\\s+"," ").trim(); }
  private static void seed(Lexicon lexicon,String methodName,String csv) throws Exception {
    if(csv==null||csv.isBlank()) return;
    Class<?> c=Class.forName("aminePlatform.util.Identifier");
    Constructor<?> ctor=c.getConstructor(String.class);
    Method add=lexicon.getClass().getMethod(methodName,c);
    Method known=lexicon.getClass().getMethod("isIdentifierKnown",String.class);
    for(String raw:csv.split(",")){
      String name=raw.trim(); if(name.isEmpty()) continue;
      if(Boolean.TRUE.equals(known.invoke(lexicon,name))) continue;
      try { add.invoke(lexicon,ctor.newInstance(name)); }
      catch(InvocationTargetException e){ Throwable cause=e.getCause()==null?e:e.getCause(); throw new IllegalStateException("seed failed "+methodName+" "+name+": "+cause,cause); }
    }
  }
  private static void applySeed(Lexicon l,String spec) throws Exception {
    if(spec==null||spec.isBlank()) return;
    for(String group:spec.split(";")){
      String[] pair=group.split("=",2); if(pair.length!=2) throw new IllegalArgumentException("bad seed "+group);
      switch(pair[0]){
        case "types" -> seed(l,"addConceptTypeEntry",pair[1]);
        case "relations" -> seed(l,"addRelationTypeEntry",pair[1]);
        case "individuals" -> seed(l,"addIndividualEntry",pair[1]);
        default -> throw new IllegalArgumentException("unknown seed category "+pair[0]);
      }
    }
  }
  public static void main(String[] args) throws Exception {
    if(args.length!=4) throw new IllegalArgumentException("expected <ontology> <program> <fixture> <seed>");
    Interpreter i=new Interpreter(args[0],new String[]{args[1]});
    Lexicon l=i.getLexicon(); if(l==null) throw new IllegalStateException("null lexicon");
    applySeed(l,args[3]);
    String input=Files.readString(Path.of(args[2]),StandardCharsets.UTF_8);
    final CG g;
    try { g=CG.parseCGIF(input,l); }
    catch(Exception e){ System.err.println("REJECT_CLASS="+e.getClass().getName()); System.err.println("REJECT_MESSAGE="+String.valueOf(e.getMessage())); System.exit(2); return; }
    if(g==null) throw new IllegalStateException("parse returned null");
    System.out.println("PARSE=accept");
    try {
      String first=g.toCGIF(l);
      if(first==null){ System.out.println("PRESERVATION=null-output"); return; }
      CG g2=CG.parseCGIF(first,l); if(g2==null) throw new IllegalStateException("reparse returned null");
      String second=g2.toCGIF(l);
      System.out.println("PRESERVATION="+(normalized(first).equals(normalized(second))?"stable_roundtrip":"changed_roundtrip"));
      System.out.println("GENERATED_BEGIN"); System.out.println(first); System.out.println("GENERATED_END");
    } catch(Exception e){ System.out.println("PRESERVATION=writer_error"); System.err.println("GENERATE_ERROR="+e.getClass().getName()+": "+e.getMessage()); }
  }
}
