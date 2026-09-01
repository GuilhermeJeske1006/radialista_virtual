const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function mensagemDeErro(response: Response): Promise<string> {
  const corpo = await response.text();
  try {
    const dados = JSON.parse(corpo);
    if (typeof dados?.detail === "string") return dados.detail;
  } catch {
    // corpo nao e JSON, usa texto cru
  }
  return corpo || `Erro ${response.status}`;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  // sessao via cookie httpOnly (setado pelo backend no login/registro) -- o
  // browser manda sozinho, sem o JS precisar ler/guardar token nenhum.
  const response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });

  // 401 aqui normalmente e' sessao expirada/ausente -- exceto no proprio /auth/login, onde
  // 401 so' significa "credenciais erradas" (login unico pra tenant e super-admin, ver
  // app/auth/router.py::login). Redirecionar nesse caso recarregava a pagina de login antes
  // do catch do form rodar, apagando a mensagem de erro sem o usuario nunca ver o motivo.
  if (response.status === 401 && path !== "/auth/login") {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Nao autenticado");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await mensagemDeErro(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// Usada pra multipart/form-data (upload de arquivo) -- nao seta content-type manualmente,
// o browser gera o boundary sozinho a partir do FormData.
export async function apiFetchForm<T>(path: string, formData: FormData, method: "POST" | "PUT" = "POST"): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { method, body: formData, credentials: "include" });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Nao autenticado");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await mensagemDeErro(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiFetchBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });

  if (!response.ok) {
    throw new ApiError(response.status, await mensagemDeErro(response));
  }

  return response.blob();
}

// Baixa a resposta de `path` (ex.: um CSV com Content-Disposition: attachment)
// direto pro disco do usuario, sem precisar de link <a> nenhum no JSX.
export async function apiFetchDownload(path: string, nomeArquivo: string): Promise<void> {
  const blob = await apiFetchBlob(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
