# Probar el instalador en un Windows 11 limpio con VirtualBox

Para la prueba 1 de [`fase-28.1-prueba-manual.md`](fase-28.1-prueba-manual.md) (y las que vengan)
sin Windows Sandbox, que solo existe en Windows Pro. La máquina virtual es un Windows recién
instalado: sin Python, Node, uv ni nada de CandidatAI, como el de alguien que llega desde el README.

Tiempo: unas 2 horas la primera vez (casi todo es esperar descargas e instalaciones). Las
siguientes, 10 minutos: se vuelve a la instantánea «Limpio» y listo.

Necesitas unos **80 GB libres** en disco (el disco virtual crece hasta 64 GB más la ISO, de unos
7 GB) y un PC con 16 GB de RAM: a la máquina virtual le das 6 GB.

---

## 1. Comprobar que el PC puede virtualizar

- [ ] Abre el Administrador de tareas (Ctrl+Mayús+Esc) → **Rendimiento** → **CPU**. Abajo a la
  derecha tiene que poner **Virtualización: Habilitado**.
  - Si pone «Deshabilitado», hay que activarla en la BIOS/UEFI del PC (suele llamarse «Intel VT-x»,
    «Intel Virtualization Technology», «SVM Mode» o «AMD-V»). Se entra pulsando F2, Supr o F10 al
    encender, según el fabricante.

## 2. Instalar VirtualBox

- [ ] Descarga el instalador de <https://www.virtualbox.org/wiki/Downloads> → **Windows hosts**.
- [ ] Ejecútalo y acepta las opciones por defecto.
  - Avisa de que la red se cortará un momento: es normal.
  - Si pide instalar «Microsoft Visual C++ Redistributable», acepta.
  - Si avisa de que faltan las «Python bindings», ignóralo: no hacen falta.

> Si tienes WSL2 instalado, VirtualBox funciona igual, pero más lento (verás una tortuga verde en la
> barra de estado de la máquina virtual). Para esta prueba basta.

## 3. Descargar Windows 11

- [ ] Ve a <https://www.microsoft.com/es-es/software-download/windows11> → sección **Descargar
  imagen de disco (ISO) de Windows 11 para dispositivos x64** → elige **Windows 11 (ISO multiedición
  para dispositivos x64)** → **Descargar ahora**.
- [ ] Idioma: **Español (España)**. Así los avisos de SmartScreen y Defender salen en español, como
  los verá quien use la guía. Se descarga un fichero `Win11_..._Spanish_x64.iso` de unos 7 GB.

Windows funciona sin activar: solo sale una marca de agua y no deja cambiar el fondo de pantalla.

## 4. Crear la máquina virtual

En VirtualBox: **Máquina → Nueva**.

- [ ] **Nombre y sistema operativo:**
  - Nombre: `Win11-prueba`.
  - Imagen ISO: la que descargaste.
  - Tipo y versión salen solos: **Microsoft Windows**, **Windows 11 (64-bit)**.
  - Deja **sin marcar** «Omitir instalación desatendida»: así VirtualBox instala Windows solo, con
    una cuenta local, y te ahorras la cuenta Microsoft que Windows exige al configurarse.
- [ ] **Instalación desatendida:**
  - Usuario: `prueba`. Contraseña: la que quieras (apúntala).
  - Marca **Instalar Guest Additions** (dejan copiar y pegar entre tu PC y la máquina virtual).
  - Edición: **Windows 11 Home**, la que tiene casi todo el mundo.
  - Si al terminar el asistente no se instala nada solo, la instalación desatendida no se guardó.
    Se lanza desde una terminal de tu PC (con la máquina virtual apagada):

    ```powershell
    & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" unattended install Win11-prueba --iso="<ruta de la ISO>" --image-index=1 --user=prueba --password=prueba --locale=es_ES --country=ES --language=es-ES --time-zone="Romance Standard Time" --install-additions --start-vm=gui
    ```

    (`--image-index=1` es Home; `VBoxManage unattended detect --iso=<ruta>` lista las ediciones).
- [ ] **Hardware:**
  - Memoria base: **4096 MB**. Con 16 GB en tu PC, 6 GB pueden no caber: la máquina virtual no
    arranca y su registro dice «Unhandled error 1455» (no hay memoria libre para reservarla).
    Cerrar WSL antes (`wsl --shutdown`) libera otros 4 GB.
  - Procesadores: **2**. Con WSL o la seguridad basada en virtualización activas, VirtualBox usa
    el motor de Hyper-V (el registro dice «AMD-V is not available» o «VT-x is not available») y
    con más procesadores y audio la máquina se cuelga a ratos.
  - En **Audio**, desmarca «Habilitar audio» (mismo motivo).
  - Deja marcado **Habilitar EFI**. VirtualBox ya pone TPM 2.0 y arranque seguro, que Windows 11
    exige.
- [ ] **Disco duro:** crear uno nuevo de **64 GB** (el mínimo de Windows 11). No marques «Reservar
  tamaño completo»: así ocupa solo lo que use.
- [ ] **Terminar.**

Antes de arrancarla, en **Configuración** de la máquina:

- [ ] **General → Avanzado → Portapapeles compartido: Bidireccional**.
- [ ] **Pantalla → Memoria de vídeo: 128 MB**.
- [ ] **Red: «Red NAT» sin IPv6**, no la «NAT» que viene. La NAT normal anuncia IPv6 a Windows
  pero no lo enruta, y la descarga de Chromium del instalador se queda colgada (falla con «No se
  pudo instalar Chromium»). Crea la red una vez desde una terminal de tu PC:

  ```powershell
  & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" natnetwork add --netname CaiNat --network 10.0.9.0/24 --enable --dhcp on --ipv6 off
  ```

  y en **Red → Adaptador 1 → Conectado a: Red NAT**, nombre `CaiNat`.

## 5. Instalar Windows

- [ ] **Iniciar.** La instalación desatendida lo hace todo sola: copia los ficheros, reinicia
  varias veces y entra en el escritorio con el usuario `prueba`. Tarda de 20 a 40 minutos. No
  toques nada mientras tanto.
- [ ] Si se queda mucho rato en **«Instalando 100 %»** (más de 30 minutos, sin uso de CPU),
  reiníciala: **Máquina → Reiniciar**. Sigue desde donde estaba y pasa a «Espera» y al escritorio.
- [ ] Si en el escritorio queda una ventana de `reg.exe` preguntando «¿Desea sobrescribirlo
  (Sí/No)?», es el script final de VirtualBox (instala las Guest Additions): escribe `S` e Intro.
- [ ] Una pantalla negra con la máquina ya instalada suele ser la pantalla apagada: mueve el ratón
  o pulsa una tecla.
- [ ] Si la instalación desatendida no arranca (pantalla negra más de 10 minutos desde el
  principio, o te pide elegir idioma), hazla a mano, como se explica en [Si la instalación
  desatendida falla](#si-la-instalación-desatendida-falla).
- [ ] Ya en el escritorio, comprueba que funciona el portapapeles: copia un texto en tu PC y pégalo
  en el Bloc de notas de la máquina virtual.
  - Si no se pega, instala a mano las Guest Additions: menú **Dispositivos → Insertar imagen de
    CD de las «Guest Additions»** → en la máquina virtual, Explorador de archivos → la unidad de
    CD → `VBoxWindowsAdditions.exe` → acepta todo → reinicia.
- [ ] Deja que Windows Update y Defender se actualicen unos 10 minutos (Configuración → Windows
  Update → Buscar actualizaciones). Así SmartScreen se comporta como en un PC normal. Reinicia si
  te lo pide.

## 6. Guardar la instantánea «Limpio»

Es lo que permite repetir la prueba desde cero las veces que haga falta.

- [ ] Apaga la máquina virtual (Inicio → Apagar). Tarda unos minutos.
- [ ] **Saca la ISO del lector:** Configuración → Almacenamiento → la unidad óptica → icono del disco
  → «Eliminar disco de la unidad virtual». Si no, al arrancar vuelve a instalar Windows desde cero
  (con EFI, el lector va antes que el disco duro).
- [ ] En VirtualBox, selecciona `Win11-prueba` → botón de la lista (☰) → **Instantáneas** →
  **Tomar**. Nombre: `Limpio`.

## 7. La prueba

Antes de empezar, comprueba en tu navegador (no en la máquina virtual) que la release existe:
<https://github.com/DiegoPrieto23/candidatai/releases/latest/download/candidatai.zip> tiene que
descargar un zip, y el mismo enlace acabado en `.sha256`, un fichero de texto.

Arranca la máquina virtual y, dentro de ella:

- [ ] **Instalar.** Abre **Windows PowerShell** desde el menú Inicio (normal, **no** como
  administrador). Da igual la carpeta en la que esté. Pega estas dos líneas:

  ```powershell
  iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1
  powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1
  ```

- [ ] **SmartScreen / Defender:** ¿sale algún aviso? Si sale, captura la pantalla (Win+Mayús+S) y
  apunta el texto exacto. Si no sale nada, apúntalo también.
- [ ] En **«2/5 · Descargar CandidatAI»** sale **«Suma SHA-256 comprobada.»**
- [ ] Termina en **«Listo. Abre «CandidatAI» desde el escritorio o el menú Inicio.»** Si falla,
  copia el error entero (con el portapapeles compartido lo pegas en tu PC).
- [ ] **Acceso directo:** doble clic en «CandidatAI» en el escritorio. Se abre una ventana negra
  (la app en marcha: no la cierres) y luego Edge en `http://127.0.0.1:8000`. La primera vez tarda
  algo más.
  - ¿Pide permiso el Firewall de Windows? Apúntalo (no debería: la app solo escucha en
    127.0.0.1).
- [ ] **Demo:**
  1. Cierra la ventana negra de CandidatAI (eso para la app).
  2. Abre una **ventana nueva** de PowerShell. Tiene que ser nueva: la del paso de instalar no
     sabe dónde está uv.
  3. Pega:

     ```powershell
     cd "$env:LOCALAPPDATA\CandidatAI\app\backend"
     uv run cai demo seed
     ```

  4. Al terminar, el comando escribe la línea para arrancar la app con la demo (empieza por
     `$env:CAI_DATA_DIR = ...; uv run cai start`). Cópiala y pégala en la misma ventana.
  5. En el navegador, con el banner «Modo demo», recorre **Inicio**, **Bandeja** y una ficha de
     oferta con CV: abre su CV y comprueba que el PDF se ve.
- [ ] **`cai doctor`:** para la app con **Ctrl+C** y, en la misma ventana:

  ```powershell
  uv run cai doctor
  ```

  Tiene que acabar en «Todo listo». Si avisa de algo, cópialo.

### Opcional: instalar como lo haría alguien desde el navegador

Para la guía de la 28.4: muchos descargarán el script con el navegador, y entonces Windows lo
marca como «descargado de internet».

- [ ] Vuelve a la instantánea «Limpio» (ver el apartado siguiente).
- [ ] En Edge, abre
  <https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1>, Ctrl+S y
  guárdalo en Descargas.
- [ ] Clic derecho en `install.ps1` → **Ejecutar con PowerShell**. Apunta qué avisos salen (de
  Edge al descargar y de Windows al ejecutar) y captúralos.

## 8. Repetir o terminar

- **Repetir desde cero:** apaga la máquina virtual → Instantáneas → selecciona `Limpio` →
  **Restaurar** (cuando pregunte, no hace falta guardar el estado actual).
- **Actualizar sin perder datos** (prueba 5 de la 28.1): no restaures; vuelve a pegar las dos
  líneas de instalar sobre la instalación que ya tienes.
- **Terminar:** cuando no la necesites, clic derecho en `Win11-prueba` → **Eliminar** → **Borrar
  todos los archivos**. Libera los 30–40 GB que ocupa.

Apunta los resultados en [`fase-28.1-prueba-manual.md`](fase-28.1-prueba-manual.md) (con qué
versión de Windows: en la máquina virtual, `winver`).

---

## Si la instalación desatendida falla

Borra la máquina virtual (clic derecho → Eliminar → Borrar todos los archivos) y créala otra vez
como en el apartado 4, pero esta vez **marca «Omitir instalación desatendida»**. Al iniciarla:

1. Pulsa una tecla cuando ponga «Press any key to boot from CD or DVD».
2. Idioma español → **Instalar Windows 11** → «**No tengo clave de producto**» → Windows 11 Pro →
   acepta la licencia → elige el disco vacío → Siguiente. Espera a que reinicie.
3. En la configuración inicial, Windows pide una cuenta Microsoft. Para crear una cuenta local:
   en la pantalla de la red (o de la cuenta), pulsa **Mayús+F10**, escribe
   `start ms-cxh:localonly` y pulsa Intro. Sale una ventana para crear el usuario `prueba`.
   - Si ese truco ya no funciona (Microsoft lo va cambiando), usa una cuenta Microsoft cualquiera:
     a la prueba no le afecta.
4. Responde «No» a todo lo de privacidad.
5. Instala las Guest Additions a mano, como en el apartado 5, y sigue desde ahí.
