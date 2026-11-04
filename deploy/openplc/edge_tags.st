(* OpenPLC program for the edge inspection station (upload in the OpenPLC web UI -> Programs).
   The station writes these tags over Modbus TCP (port 502):
     %QX0.0  reject_coil  <- Modbus coil 0, pulses 0.5 s on every trigger
     %QW0    part_count   <- Modbus holding register 0, number of triggers since the station started
   The program copies the reject pulse to reject_lamp (%QX0.1) and counts rejects itself, so the
   "tag change" is visible in OpenPLC -> Monitoring. Hardware layer: "Blank" (no physical I/O), because
   the Pi's GPIO17/27 are already driven by the station. *)
PROGRAM edge_tags
  VAR
    reject_coil AT %QX0.0 : BOOL;
    reject_lamp AT %QX0.1 : BOOL;
    part_count AT %QW0 : WORD;
    plc_reject_total AT %QW1 : WORD;
    last_coil : BOOL;
  END_VAR

  reject_lamp := reject_coil;
  IF reject_coil AND NOT last_coil THEN
    plc_reject_total := plc_reject_total + 1;
  END_IF;
  last_coil := reject_coil;
END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms, PRIORITY := 0);
    PROGRAM instance0 WITH task0 : edge_tags;
  END_RESOURCE
END_CONFIGURATION
