# Evidencia en video — Login y panel de administración multi-tenant

**Proyecto:** ElectroMap — Kevin Zapata Dávila
**Corresponde a:** Épica 003 (Funcionalidad y seguridad: control de acceso multi-tenant), Etapas 1 a 9.
**Respaldo:** 9 Pull Requests en GitHub, 49 pruebas automáticas (pytest).

**Video:** https://drive.google.com/file/d/1nQMXy1VdtuW3iQVnxDy-SPtbgfIVZrhS/view?usp=drive_link

## Contenido mostrado

- Login con autenticación JWT.
- Panel de administración con los tres roles del sistema: VSC, empresa y cliente.
- Aislamiento multi-tenant: cada rol ve y puede modificar solo lo que le corresponde según su nivel de acceso (ver `claude/Proceso_Asignacion_Accesos.md` y Documento 05 — Documento de Diseño para el detalle de las reglas).
