import { Injectable } from '@angular/core';
import { CryptoService } from './crypto.service';
import { AuthService } from './auth.service';

const CHUNK_SIZE = 8 * 1024 * 1024; // 8 MB plaintext per block

const BLOCK_OVERHEAD = 4 + 12 + 16; // Länge + IV + GCM-Tag
const SALT_SIZE = 16;

/** Liest exakt n Bytes aus einem Stream, ohne den Puffer bei jedem Netzwerk-Chunk neu zu kopieren. */
class StreamReader {
  private chunks: Uint8Array[] = [];
  private buffered = 0;
  constructor(private reader: ReadableStreamDefaultReader<Uint8Array>) {}

  async readExactly(n: number): Promise<Uint8Array<ArrayBuffer> | null> {
    while (this.buffered < n) {
      const { done, value } = await this.reader.read();
      if (done) return null;
      this.chunks.push(value);
      this.buffered += value.byteLength;
    }
    const result = new Uint8Array(n);
    let offset = 0;
    while (offset < n) {
      const head = this.chunks[0];
      const take = Math.min(head.byteLength, n - offset);
      result.set(head.subarray(0, take), offset);
      offset += take;
      if (take === head.byteLength) this.chunks.shift();
      else this.chunks[0] = head.subarray(take);
    }
    this.buffered -= n;
    return result;
  }
}

export interface UploadResult {
  token: string;
  expires_at: string | null;
  download_url: string;
  ps_cmd: string;
  sh_cmd: string;
}

@Injectable({ providedIn: 'root' })
export class TransferService {
  constructor(
    private crypto: CryptoService,
    private auth: AuthService,
  ) {}

  async uploadFile(
    file: File,
    password: string,
    expiresIn: string,
    onProgress: (pct: number) => void,
  ): Promise<UploadResult> {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const key  = await this.crypto.deriveKey(password, salt);

    const totalSize = file.size;
    const blocks    = Math.ceil(totalSize / CHUNK_SIZE);
    const totalOut  = SALT_SIZE + totalSize + blocks * BLOCK_OVERHEAD;
    const cryptoSvc = this.crypto;
    let offset = 0;
    let sent   = SALT_SIZE;

    // Datei in echten 8-MB-Blöcken lesen und verschlüsseln (file.stream() liefert nur ~64-KB-Stücke)
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(salt);
      },
      async pull(controller) {
        if (offset >= totalSize) {
          controller.close();
          return;
        }
        const plain = new Uint8Array(await file.slice(offset, offset + CHUNK_SIZE).arrayBuffer());
        offset += plain.byteLength;
        const encrypted = await cryptoSvc.encryptChunk(key, plain);
        sent += encrypted.byteLength;
        onProgress(Math.min(99, Math.round((sent / totalOut) * 100)));
        controller.enqueue(encrypted);
      },
    }, { highWaterMark: 1 });

    const token = this.auth.getToken();
    const response = await fetch('/api/upload', {
      method: 'POST',
      // duplex: 'half' ist für Streaming-Bodies nötig, fehlt aber noch in den TS-DOM-Typen
      duplex: 'half',
      body,
      headers: {
        'X-Filename':   encodeURIComponent(file.name),
        'X-Expires-In': expiresIn,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    } as RequestInit & { duplex: 'half' });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Upload fehlgeschlagen (${response.status}): ${text}`);
    }

    onProgress(100);
    return response.json();
  }

  async downloadAndDecrypt(
    token: string,
    password: string,
    filename: string,
    onProgress: (pct: number) => void,
  ): Promise<void> {
    const handle   = await (window as any).showSaveFilePicker({ suggestedName: filename });
    const writable = await handle.createWritable();

    try {
      const response = await fetch(`/api/download/${token}`);
      if (!response.ok) throw new Error(`Download fehlgeschlagen (${response.status})`);

      const total   = parseInt(response.headers.get('content-length') ?? '0', 10);
      let received  = 0;
      const sr      = new StreamReader(response.body!.getReader());

      const saltBytes = await sr.readExactly(SALT_SIZE);
      if (!saltBytes) throw new Error('Ungültige Datei – Salt fehlt');
      received += SALT_SIZE;
      const key = await this.crypto.deriveKey(password, saltBytes);

      while (true) {
        const lenBytes = await sr.readExactly(4);
        if (!lenBytes) break;
        const blockLen = new DataView(lenBytes.buffer).getUint32(0, false);
        const iv       = await sr.readExactly(12);
        const tag      = await sr.readExactly(16);
        const cipher   = await sr.readExactly(blockLen);
        if (!iv || !tag || !cipher) throw new Error('Unvollständiger Block');

        const plaintext = await this.crypto.decryptChunk(key, iv, tag, cipher);
        await writable.write(plaintext);

        received += BLOCK_OVERHEAD + blockLen;
        if (total > 0) onProgress(Math.min(99, Math.round((received / total) * 100)));
      }

      await writable.close();
      onProgress(100);
    } catch (e) {
      await writable.abort();
      throw e;
    }
  }
}
