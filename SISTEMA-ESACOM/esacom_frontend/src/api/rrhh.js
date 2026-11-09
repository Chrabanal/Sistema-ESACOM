import client from "./client";

export async function auditarRRHHArchivo(archivo) {
  const form = new FormData();
  form.append("archivo", archivo);
  const { data } = await client.post("/rrhh/auditoria/", form);
  return data;
}

export async function auditarRRHHConfigurado() {
  const { data } = await client.get("/rrhh/auditoria/");
  return data;
}
