with open('templates/caja.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Buscamos el fragmento que empieza con "<div class=\"modal-body text-center p-4\">"
# y termina con "</div>\n</div>\n</div>\n"
start_idx = -1
for i, line in enumerate(lines):
    if 'Para cerrar la caja' in line:
        # El fragmento suele empezar unas lineas antes
        for j in range(i, i-5, -1):
            if '<div class="modal-body text-center p-4">' in lines[j]:
                start_idx = j
                break
        if start_idx != -1:
            break

if start_idx != -1:
    # El fragmento termina 13-15 lineas despues
    end_idx = start_idx + 13
    # Verificamos que termine en </div>
    while end_idx < len(lines) and '</div>' in lines[end_idx]:
        end_idx += 1
    
    del lines[start_idx:end_idx]
    
    with open('templates/caja.html', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Fragmento eliminado correctamente")
else:
    print("No se encontró el fragmento")
