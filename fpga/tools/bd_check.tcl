# Build a block design from Tcl in memory, validate it, generate its targets and
# write it back as a native Tcl script of this Vivado version.
# env: BD_TCL (script), BD_HDL (hdl_sources.tcl or ""), PART, OUT_TCL
create_project -part $::env(PART) -in_memory
set_property source_mgmt_mode All [current_project]
if {$::env(BD_HDL) ne ""} { source $::env(BD_HDL) }
update_compile_order -fileset sources_1
set name [file rootname [file tail $::env(BD_TCL)]]
create_bd_design -dir . $name
set rc [catch {source $::env(BD_TCL)} msg]
puts "BD_SOURCE rc=$rc $msg"
set rc [catch {validate_bd_design} msg]
puts "BD_VALIDATE rc=$rc"
write_bd_tcl -force -no_ip_version $::env(OUT_TCL)
set rc [catch {generate_target all [get_files $name.bd]} msg]
puts "BD_GENERATE rc=$rc"
report_ip_status
