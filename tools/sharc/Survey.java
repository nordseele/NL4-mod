// Summarize an analyzed SHARC program: memory blocks, function count,
// disassembly errors, and a couple of decompiled samples.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.address.*;

public class Survey extends GhidraScript {
	@Override
	public void run() throws Exception {
		for (MemoryBlock b : currentProgram.getMemory().getBlocks())
			println(String.format("BLOCK %s %s-%s %d", b.getName(), b.getStart(), b.getEnd(), b.getSize()));
		FunctionManager fm = currentProgram.getFunctionManager();
		println("FUNCTIONS " + fm.getFunctionCount());
		int insns = 0;
		InstructionIterator it = currentProgram.getListing().getInstructions(true);
		while (it.hasNext()) { it.next(); insns++; }
		println("INSTRUCTIONS " + insns);
		int bm = 0;
		var bmi = currentProgram.getBookmarkManager().getBookmarksIterator("Error");
		while (bmi.hasNext()) { var b = bmi.next(); if (bm < 15) println("ERRBM " + b.getAddress() + " " + b.getComment()); bm++; }
		println("ERROR_BOOKMARKS " + bm);
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		int ok = 0, fail = 0, n = 0;
		for (Function f : fm.getFunctions(true)) {
			DecompileResults r = di.decompileFunction(f, 20, monitor);
			if (r.decompileCompleted()) ok++; else fail++;
			n++;
		}
		println("DECOMPILE ok=" + ok + " fail=" + fail);
	}
}
