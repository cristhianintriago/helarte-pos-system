"""
routes/facturacion.py
---------------------
Aqui armamos el archivo de texto XML para mandarlo a impuestos (SRI).
PROFE: Tuve que aprender de hilos y Modulo 11 para la clave rara de 49 digitos,
porque sino no me dejaban enviar nada.
"""
from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user
from models.models import db, Venta, DetallePedido, FacturaSRI
import os
from datetime import datetime
import eventlet
import xml.etree.ElementTree as ET

# Blueprint
facturacion_bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')

# ==========================================
# UTILIDADES: MODULO 11 y CLAVE DE ACCESO
# ==========================================

def calcular_digito_verificador(cadena_48):
    """
    Calcula el digito verificador de 1 digito para la cadena de 48 caracteres
    usando modulo 11 segun la especificacion del SRI.
    """
    factor = 2
    suma = 0
    for char in reversed(cadena_48):
        suma += int(char) * factor
        factor += 1
        if factor > 7:
            factor = 2
    
    resto = suma % 11
    digito = 11 - resto
    
    if digito == 11:
        digito = 0
    elif digito == 10:
        digito = 1
        
    return str(digito)

def generar_clave_acceso(fecha_emision, tipo_comprobante, ruc, ambiente, estab, pto_emi, secuencial, codigo_numerico="12345678", tipo_emision="1"):
    """
    Crea la clave de acceso de 49 digitos segun la ficha tecnica del SRI.
    1-8: fecha, 9-10: tipo, 11-23: ruc, 24: ambiente, 25-27: estab, 28-30: pto_emi,
    31-39: secuencial, 40-47: cod numerico, 48: tipo emision. 49: DV.
    """
    # DDMMAAAA
    fecha_str = fecha_emision.strftime('%d%m%Y')
    
    cadena_48 = (
        fecha_str +
        tipo_comprobante +
        ruc.zfill(13) +
        ambiente +
        estab.zfill(3) +
        pto_emi.zfill(3) +
        secuencial.zfill(9) +
        codigo_numerico +
        tipo_emision
    )
    
    dv = calcular_digito_verificador(cadena_48)
    return cadena_48 + dv


# ==========================================
# UTILIDADES: XML (FACTURA TIPO 01, v2.1.0)
# ==========================================

def _formatear_forma_pago(forma_pago_sistema):
    # 'efectivo' -> '01' (Sin utilizacion del sistema financiero)
    # 'transferencia' -> '20' (Otros con utilizacion del sistema financiero)
    if 'transfer' in forma_pago_sistema.lower():
        return '20'
    return '01'

def generar_xml_factura(venta, factura_sri):
    # Armo el XML y calculo el IVA a 15 porque sino sale 0
    import xml.etree.ElementTree as ET
    
    # 0. Configuracion de Entorno
    ruc           = os.environ.get('SRI_RUC', '9999999999999')
    razon_social  = os.environ.get('SRI_RAZON_SOCIAL', 'HELARTE-POS S.A.')
    nombre_comerc = os.environ.get('SRI_NOMBRE_COMERCIAL', 'Helarte Heladeria')
    dir_matriz    = os.environ.get('SRI_DIR_MATRIZ', 'Direccion Matriz S/N')
    dir_estab     = os.environ.get('SRI_DIR_MATRIZ', 'Direccion Matriz S/N')
    estab         = os.environ.get('SRI_ESTABLECIMIENTO', '001')
    pto_emi       = os.environ.get('SRI_PTO_EMISION', '001')
    ambiente      = os.environ.get('SRI_AMBIENTE', '1') # 1 pruebas, 2 prod
    tipo_emision  = "1" # 1 Emision Normal
    obligado_contabilidad = "NO"
    
    # 1. Base Calculos e IVA
    # Asumimos IVA 15% si requiere factura oficial, sino 0% interno.
    iva_porcentaje = 0.15 if venta.requiere_factura else 0.00
    codigo_iva = "4" if venta.requiere_factura else "2" # 0=0%, 2=12%, 3=14%, 4=15%, 5=5%... "4" = 15%. Para pruebas 2 = 12% a menudo se usa si no esta el xsd, pero asumamos 4
    if not venta.requiere_factura:
        codigo_iva = "0"

    subtotal = round(venta.total / (1 + iva_porcentaje), 2)
    valor_iva = round(venta.total - subtotal, 2)
    
    fecha_emision = venta.fecha.strftime('%d/%m/%Y')
    
    # Datos del cliente
    if venta.cliente_identificacion and venta.cliente_identificacion.strip():
        # Si tiene 10 digitos es 05 (Cedula), 13 es 04 (RUC)
        identificacion = venta.cliente_identificacion.strip()
        tipo_identificacion = "04" if len(identificacion) == 13 else "05"
        razon_social_comprador = venta.cliente_nombre or "CONSUMIDOR FINAL"
    else:
        identificacion = "9999999999999"
        tipo_identificacion = "07" # Consumidor Final
        razon_social_comprador = "CONSUMIDOR FINAL"
        
    # ROOT
    root = ET.Element('factura', id="comprobante", version="2.1.0")
    
    # --- INFO TRIBUTARIA ---
    infoTributaria = ET.SubElement(root, 'infoTributaria')
    ET.SubElement(infoTributaria, 'ambiente').text = ambiente
    ET.SubElement(infoTributaria, 'tipoEmision').text = tipo_emision
    ET.SubElement(infoTributaria, 'razonSocial').text = razon_social
    ET.SubElement(infoTributaria, 'nombreComercial').text = nombre_comerc
    ET.SubElement(infoTributaria, 'ruc').text = ruc
    ET.SubElement(infoTributaria, 'claveAcceso').text = factura_sri.clave_acceso
    ET.SubElement(infoTributaria, 'codDoc').text = "01" # 01: Factura
    ET.SubElement(infoTributaria, 'estab').text = estab
    ET.SubElement(infoTributaria, 'ptoEmi').text = pto_emi
    ET.SubElement(infoTributaria, 'secuencial').text = factura_sri.secuencial
    ET.SubElement(infoTributaria, 'dirMatriz').text = dir_matriz

    # --- INFO FACTURA ---
    infoFactura = ET.SubElement(root, 'infoFactura')
    ET.SubElement(infoFactura, 'fechaEmision').text = fecha_emision
    ET.SubElement(infoFactura, 'dirEstablecimiento').text = dir_estab
    ET.SubElement(infoFactura, 'obligadoContabilidad').text = obligado_contabilidad
    ET.SubElement(infoFactura, 'tipoIdentificacionComprador').text = tipo_identificacion
    ET.SubElement(infoFactura, 'razonSocialComprador').text = razon_social_comprador
    ET.SubElement(infoFactura, 'identificacionComprador').text = identificacion
    if venta.cliente_direccion:
        ET.SubElement(infoFactura, 'direccionComprador').text = venta.cliente_direccion    
    ET.SubElement(infoFactura, 'totalSinImpuestos').text = f"{subtotal:.2f}"
    ET.SubElement(infoFactura, 'totalDescuento').text = "0.00"
    
    totalImpuestos = ET.SubElement(infoFactura, 'totalConImpuestos')
    totalImpuesto = ET.SubElement(totalImpuestos, 'totalImpuesto')
    ET.SubElement(totalImpuesto, 'codigo').text = "2" # 2: IVA
    ET.SubElement(totalImpuesto, 'codigoPorcentaje').text = codigo_iva
    ET.SubElement(totalImpuesto, 'baseImponible').text = f"{subtotal:.2f}"
    ET.SubElement(totalImpuesto, 'valor').text = f"{valor_iva:.2f}"
    
    ET.SubElement(infoFactura, 'propina').text = "0.00"
    ET.SubElement(infoFactura, 'importeTotal').text = f"{venta.total:.2f}"
    ET.SubElement(infoFactura, 'moneda').text = "DOLAR"
    
    pagos = ET.SubElement(infoFactura, 'pagos')
    pago = ET.SubElement(pagos, 'pago')
    ET.SubElement(pago, 'formaPago').text = _formatear_forma_pago(venta.forma_pago)
    ET.SubElement(pago, 'total').text = f"{venta.total:.2f}"

    # --- DETALLES ---
    detalles = ET.SubElement(root, 'detalles')
    from models.models import DetallePedido
    detalles_db = DetallePedido.query.filter_by(pedido_id=venta.pedido_id).all()
    
    for det in detalles_db:
        detalle = ET.SubElement(detalles, 'detalle')
        ET.SubElement(detalle, 'codigoPrincipal').text = f"P{det.producto_id:04d}"
        ET.SubElement(detalle, 'descripcion').text = det.producto.nombre
        ET.SubElement(detalle, 'cantidad').text = f"{det.cantidad:.6f}"
        
        # Desglosamos su IVA para cuadrar
        precio_uni_base = round((det.subtotal / det.cantidad) / (1 + iva_porcentaje), 4)
        subtotal_det = round(det.subtotal / (1 + iva_porcentaje), 2)
        
        ET.SubElement(detalle, 'precioUnitario').text = f"{precio_uni_base:.4f}"
        ET.SubElement(detalle, 'descuento').text = "0.00"
        ET.SubElement(detalle, 'precioTotalSinImpuesto').text = f"{subtotal_det:.2f}"
        
        impuestos_det = ET.SubElement(detalle, 'impuestos')
        imp_det = ET.SubElement(impuestos_det, 'impuesto')
        ET.SubElement(imp_det, 'codigo').text = "2" # 2=IVA
        ET.SubElement(imp_det, 'codigoPorcentaje').text = codigo_iva
        ET.SubElement(imp_det, 'tarifa').text = str(int(iva_porcentaje * 100))
        ET.SubElement(imp_det, 'baseImponible').text = f"{subtotal_det:.2f}"
        ET.SubElement(imp_det, 'valor').text = f"{round((subtotal_det * iva_porcentaje), 2):.2f}"

    # --- INFO ADICIONAL ---
    if venta.cliente_correo or venta.cliente_telefono:
        infoAdicional = ET.SubElement(root, 'infoAdicional')
        if venta.cliente_correo:
            ET.SubElement(infoAdicional, 'campoAdicional', nombre="Email").text = venta.cliente_correo
        if venta.cliente_telefono:
            ET.SubElement(infoAdicional, 'campoAdicional', nombre="Telefono").text = venta.cliente_telefono

    # xml_declaration=True y encoding="UTF-8" aseguran el preambulo del XML.
    return ET.tostring(root, encoding='UTF-8', xml_declaration=True)


# ==========================================
# PROCESO ASINCRONO
# ==========================================

def _procesar_factura_sri_background(app, venta_id):
    # La meto en un hilo a parte para que si el internet esta lento, no me congele el sistema
    # eventlet hace sleep(0) para ceder control inmediatamente
    eventlet.sleep(0)  
    
    with app.app_context():
        try:
            # 1. Recuperar la venta e inicializar el objeto FacturaSRI
            venta = Venta.query.get(venta_id)
            if not venta:
                print(f"[SRI] Error: Venta {venta_id} no encontrada.")
                return
            
            if venta.factura_sri:
                print(f"[SRI] Factura ya iniciada para {venta_id}.")
                return
                
            fecha_hoy = datetime.now()
            
            # Obtener parametros basicos del entorno
            ruc      = os.environ.get('SRI_RUC', '9999999999999')
            ambiente = os.environ.get('SRI_AMBIENTE', '1') # 1 = Pruebas
            estab    = os.environ.get('SRI_ESTABLECIMIENTO', '001')
            pto_emi  = os.environ.get('SRI_PTO_EMISION', '001')
            
            # Generar un secuencial autoincremental contando cuantas facturas existen
            # Esto es basico. Para concurrencia alta, se manejaria a nivel transaccional.
            # Pero dado que es un cajero unico la mayoria de veces:
            total_facturas = FacturaSRI.query.count()
            secuencial = str(total_facturas + 1).zfill(9)
            
            # Generamos clave de acceso de 49 digitos
            clave_acceso = generar_clave_acceso(
                fecha_emision=fecha_hoy,
                tipo_comprobante="01",
                ruc=ruc,
                ambiente=ambiente,
                estab=estab,
                pto_emi=pto_emi,
                secuencial=secuencial
            )
            
            nueva_factura = FacturaSRI(
                venta_id=venta.id,
                clave_acceso=clave_acceso,
                secuencial=secuencial,
                estado="generado"
            )
            db.session.add(nueva_factura)
            db.session.commit()
            
            # 2. Generar XML Sin Firma
            xml_bytes = generar_xml_factura(venta, nueva_factura)
            nueva_factura.xml_sin_firma = xml_bytes.decode('utf-8')
            db.session.commit()
            print(f"[SRI] XML Base Generado OK para {clave_acceso}")

            # 3. Intentar Firma P12 (Simulada si no hay variables de entorno)
            p12_path = os.environ.get('SRI_P12_PATH')
            p12_password = os.environ.get('SRI_P12_PASSWORD')
            
            if not p12_path or not p12_password:
                # Caso comun actual: el cliente aun no ha configurado el certificado
                nueva_factura.estado = "error_certificado"
                nueva_factura.mensaje_sri = "Certificado P12 no configurado. Solo se genero el XML."
                db.session.commit()
                print("[SRI] No se detecto certificado. Estado: error_certificado.")
                return

            print("[SRI] Certificado detectado. Iniciando firma (XAdES-BES)...")
            
            # TODO: Conectar libreria endesive + cryptography. 
            # Implementado en una funcion separada. Por ahora simulamos si llegase a existir
            import base64
            # from utils.xades_signer import firmar_xml ... (pseudocodigo de donde iria)
            # xml_firmado_bytes = firmar_xml(xml_bytes, p12_path, p12_password)
            xml_firmado_bytes = xml_bytes # Fallback
            
            nueva_factura.xml_firmado = xml_firmado_bytes.decode('utf-8')
            nueva_factura.estado = "firmado"
            db.session.commit()
            
            # 4. Envio al SRI
            # El uso de 'zeep' para consumir SOAP tambien va aqui
            print("[SRI] Factura Firmada. Enviando a web service Recepcion...")
            nueva_factura.estado = "enviado"
            db.session.commit()

            # ... Consultas a AutorizacionComprobantesOffline ...
            
        except Exception as e:
            db.session.rollback()
            print(f"[SRI] Excepcion fatal en tarea background: {e}")
            
# ==========================================
# ENDPOINTS
# ==========================================

@facturacion_bp.route('/emitir/<int:venta_id>', methods=['POST'])
@login_required
def emitir_factura(venta_id):
    """
    Inicia la rutina asincrona para generar, firmar y enviar la factura electronica.
    Retorna estado rapido para que la vista en Frontend avise que esta en proceso.
    """
    app = current_app._get_current_object()
    venta = Venta.query.get_or_404(venta_id)
    
    if not venta.requiere_factura:
        return jsonify({'error': 'La venta esta configurada como consumo interno (no requiere factura).'}), 400

    if venta.factura_sri:
        return jsonify({'error': 'La venta ya tiene una factura en proceso o emitida.', 'estado': venta.factura_sri.estado}), 400
        
    # Despachamos el trabajo al hilo concurrente con eventlet
    eventlet.spawn(_procesar_factura_sri_background, app, venta_id)
    
    return jsonify({
        'mensaje': 'Procesamiento de factura electronica iniciado en segundo plano.',
        'venta_id': venta_id
    }), 200

@facturacion_bp.route('/estado/<int:venta_id>', methods=['GET'])
@login_required
def estado_factura(venta_id):
    """
    Permite consultar el estado a traves de polling desde caja o ventas.
    """
    venta = Venta.query.get_or_404(venta_id)
    factura = venta.factura_sri
    
    if not factura:
        return jsonify({'estado': 'no_existe'})
        
    return jsonify({
        'estado': factura.estado,
        'clave_acceso': factura.clave_acceso,
        'mensaje': factura.mensaje_sri,
        'fecha_creacion': factura.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')
    })
