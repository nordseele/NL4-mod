"""Decompile every function of an ELF to one greppable text file (headless Ghidra via pyghidra).

Runs in a throwaway container so it never touches the project the MCP server has open:
  docker run --rm --entrypoint python -v "$PWD/ghidra/bin":/work -v "$PWD/tools":/tools \
    ghcr.io/clearbluejar/pyghidra-mcp:sha-f43400b /tools/dump_decomp.py /work/nl4_os132_full.elf /work/decomp.c
"""
import sys, tempfile
import pyghidra

elf, out = sys.argv[1], sys.argv[2]
pyghidra.start()
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

with tempfile.TemporaryDirectory() as tmp, \
        pyghidra.open_program(elf, project_location=tmp, project_name='dump', analyze=False,
                              language='ARM:LE:32:v5t') as flat:
    prog = flat.getCurrentProgram()
    # operator_new calls the bad_alloc thrower; this analyzer then flags operator_new itself
    # as non-returning and stops disassembling after every `new`. Turn it off before analysis.
    opts = prog.getOptions('Analyzers')
    name = 'Non-Returning Functions - Discovered'
    tx = prog.startTransaction('options')
    opts.setBoolean(name, False)
    prog.endTransaction(tx, True)
    print(name, '=', opts.getBoolean(name, True))
    flat.analyzeAll(prog)
    ifc = DecompInterface()
    ifc.openProgram(prog)
    mon = ConsoleTaskMonitor()
    n = fails = 0
    with open(out, 'w') as f:
        for fn in prog.getFunctionManager().getFunctions(True):
            res = ifc.decompileFunction(fn, 60, mon)
            n += 1
            f.write(f'\n// ===== {fn.getName()} @ {fn.getEntryPoint()} size={fn.getBody().getNumAddresses()}\n')
            if res.decompileCompleted():
                f.write(res.getDecompiledFunction().getC())
            else:
                fails += 1
                f.write(f'// decompile failed: {res.getErrorMessage()}\n')
    print(f'{n} fonctions, {fails} échecs -> {out}')
