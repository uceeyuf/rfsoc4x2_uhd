# Elaborate key RFNoC modules (called by elab_check.sh).
set srcs [split [string trim [read [open $::env(SRCS)]]] "\n"]
set incdirs {}; foreach f $srcs { lappend incdirs [file dirname $f] }; set incdirs [lsort -unique $incdirs]
foreach f $srcs {
  if {[string match *x4xx_qsfp_wrapper* $f] || [string match *x4xx_mgt_io_core* $f] || [string match *rfnoc_ta_x4xx_eth.sv $f]} continue
  set e [file extension $f]
  if {$e eq ".vhd"} { read_vhdl $f } elseif {$e eq ".sv"} { read_verilog -sv $f } elseif {$e eq ".v"} { read_verilog $f }
}
set results {}
foreach {top gen} {
  chdr_stream_endpoint {}
  rfnoc_block_radio {}
  chdr_crossbar_nxn {}
  eth_ipv4_interface_wrapper {PREAMBLE_BYTES=0 ADD_SOF=0 PAUSE_EN=1 ENET_W=512 CPU_W=64 CHDR_W=512 CHDR_FIFO_SIZE=16}
  rfnoc_core_kernel {NUM_BLOCKS=6 NUM_STREAM_ENDPOINTS=6 NUM_ENDPOINTS_CTRL=1 NUM_TRANSPORTS=2 NUM_EDGES=12 DEVICE_FAMILY="ULTRASCALE"}
} {
  set args [list -rtl -top $top -part xczu48dr-ffvg1517-2-e -include_dirs $incdirs -mode out_of_context]
  if {$gen ne ""} { lappend args -generic $gen }
  set rc [catch {synth_design {*}$args} msg]
  lappend results "$top rc=$rc"
  catch {close_design}
}
puts "ELAB_SUMMARY: $results"
