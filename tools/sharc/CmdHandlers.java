// Disassemble and create functions at the DSP command handlers read from the table at dm:0x92180.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;

public class CmdHandlers extends GhidraScript {
	@Override
	public void run() throws Exception {
		AddressSpace dm = currentProgram.getAddressFactory().getAddressSpace("dm");
		AddressSpace sw = currentProgram.getAddressFactory().getAddressSpace("sw");
		for (int i = 0; i < 27; i++) {
			long target = getInt(toAddr(String.format("dm:%x", 0x92180 + i))) & 0xffffffffL;
			Address a = toAddr(String.format("sw:%x", target));
			disassemble(a);
			if (getFunctionAt(a) == null) createFunction(a, String.format("dsp_cmd_%02d", i));
			else getFunctionAt(a).setName(String.format("dsp_cmd_%02d", i), ghidra.program.model.symbol.SourceType.USER_DEFINED);
		}
		println("HANDLERS DONE");
	}
}
