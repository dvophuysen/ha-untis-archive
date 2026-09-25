// Ein Foto oder PDF als Material ablegen: derselbe Weg für die Materialien und
// für „Scannen“ der Eltern (D183), keine zweite Pipeline. Der Server liest die
// Datei danach selbst; die Felder sind nur Hinweise.
import { api } from './api.js';

export async function uploadMaterial(accountId, file, fields = {}) {
  const body = new FormData();
  body.append('file', file);
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== '') body.append(key, String(value));
  }
  return api.post(`/api/accounts/${accountId}/materials`, body);
}
