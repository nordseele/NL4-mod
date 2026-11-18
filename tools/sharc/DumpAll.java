// Decompile every function of the current SHARC program into one text file (arg 0 = output path).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DumpAll extends GhidraScript {
	@Override
	public void run() throws Exception {
		String out = getScriptArgs()[0];
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		try (PrintWriter w = new PrintWriter(new FileWriter(out))) {
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				DecompileResults r = di.decompileFunction(f, 60, monitor);
				w.println("// ===== " + f.getName() + " @ " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
				w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// FAILED " + r.getErrorMessage());
			}
		}
		println("DUMPED " + out);
	}
}
