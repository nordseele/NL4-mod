// Print every instruction (address, bytes, text) plus function starts (arg 0 = output path).
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.*;

public class ListAll extends GhidraScript {
	@Override
	public void run() throws Exception {
		Listing l = currentProgram.getListing();
		FunctionManager fm = currentProgram.getFunctionManager();
		try (PrintWriter w = new PrintWriter(new FileWriter(getScriptArgs()[0]))) {
			for (Instruction i : l.getInstructions(true)) {
				Function f = fm.getFunctionAt(i.getAddress());
				if (f != null) w.println("\n; ===== " + f.getName());
				w.println(i.getAddress() + "  " + i);
			}
		}
		println("LISTED");
	}
}
