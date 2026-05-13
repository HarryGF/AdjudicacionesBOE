def exportar_informe_legible(adjudicatarios, fecha):
    """Genera un .txt con los adjudicatarios en formato legible por humanos."""
    os.makedirs("Adjudicaciones_Filtradas", exist_ok=True)
    ruta = f"Adjudicaciones_Filtradas/Informe_{fecha}.txt"
 
    fecha_formateada = f"{fecha[:4]}/{fecha[4:6]}/{fecha[6:]}"
    separador = "═" * 60
 
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"INFORME DE ADJUDICACIONES BOE — {fecha_formateada}\n")
        f.write(f"{separador}\n\n")
 
        for i, (id_boe, datos) in enumerate(adjudicatarios.items(), start=1):
            f.write(f"[{i}] {id_boe}\n")
            f.write(f"    Objeto      : {datos.get('Objeto', 'No disponible')}\n")
            f.write(f"    Expediente  : {datos.get('Expediente', 'No disponible')}\n")
            f.write(f"    CPV         : {', '.join(datos.get('CPV Coincidentes', []))}\n")
            f.write(f"    PDF         : {datos.get('PDF', '')}\n")
            f.write(f"\n")
 
            # Recorremos los lotes (General u otros), ignorando los campos de cabecera
            campos_cabecera = {"Objeto", "Expediente", "CPV Coincidentes", "PDF"}
            lotes = {k: v for k, v in datos.items() if k not in campos_cabecera}
 
            for lote_nombre, lote_datos in lotes.items():
                if not isinstance(lote_datos, dict):
                    continue
 
                if lote_nombre != "General":
                    f.write(f"    ── {lote_nombre} ──\n")
 
                f.write(f"    Empresa     : {lote_datos.get('Nombre Adjudicatario', '')}\n")
                f.write(f"    NIF         : {lote_datos.get('NIF', '')}\n")
                f.write(f"    Dirección   : {lote_datos.get('Direccion', '')}\n")
                f.write(f"    Localidad   : {lote_datos.get('Localidad', '')} "
                        f"({lote_datos.get('Codigo Postal', '')}) — "
                        f"{lote_datos.get('Pais', '')}\n")
                f.write(f"    Importe     : {lote_datos.get('Importe', '')} €\n")
                f.write(f"    PYME        : {lote_datos.get('PYME', '').upper()}\n")
                f.write(f"\n")
 
            f.write(f"{separador}\n\n")
 
    print(f"Informe legible exportado a: {ruta}")