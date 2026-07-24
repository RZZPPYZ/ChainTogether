import type { PersonaRead } from ".";

const API = `${window.location.origin}/api/personas`;

function headers(token: string): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body && typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function fetchPersonas(token: string): Promise<PersonaRead[]> {
  return json(await fetch(API, { headers: headers(token) }));
}

export async function importPersona(
  token: string,
  sourceUrl: string
): Promise<PersonaRead> {
  return json(
    await fetch(`${API}/import`, {
      method: "POST",
      headers: headers(token),
      body: JSON.stringify({ source_url: sourceUrl }),
    })
  );
}

export async function importPersonaZip(
  token: string,
  file: File
): Promise<PersonaRead> {
  const form = new FormData();
  form.append("file", file, file.name);
  return json(
    await fetch(`${API}/import-zip`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    })
  );
}

export async function deletePersona(token: string, personaId: string): Promise<void> {
  const response = await fetch(`${API}/${personaId}`, {
    method: "DELETE",
    headers: headers(token),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body && typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`
    );
  }
}
