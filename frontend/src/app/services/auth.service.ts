import { Injectable } from '@angular/core';

const STORAGE_KEY = 'dap_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private accessToken: string | null = null;

  async login(username: string, password: string, rememberMe: boolean): Promise<void> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, remember_me: rememberMe }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? 'Login fehlgeschlagen');
    }
    const data = await res.json();
    this.setToken(data.access_token);
  }

  // Called once on app startup (see app.config.ts APP_INITIALIZER). Restores
  // the access token from localStorage on reload without a network round
  // trip; only falls back to the httpOnly refresh-cookie flow (which needs
  // "Angemeldet bleiben" at login) if no valid token is stored.
  async tryAutoLogin(): Promise<boolean> {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && this.isTokenValid(stored)) {
      this.accessToken = stored;
      return true;
    }

    try {
      const res = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' });
      if (!res.ok) {
        localStorage.removeItem(STORAGE_KEY);
        return false;
      }
      const data = await res.json();
      this.setToken(data.access_token);
      return true;
    } catch {
      return false;
    }
  }

  async logout(): Promise<void> {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    this.accessToken = null;
    localStorage.removeItem(STORAGE_KEY);
  }

  getToken(): string | null {
    return this.accessToken;
  }

  isLoggedIn(): boolean {
    return this.accessToken !== null;
  }

  private setToken(token: string): void {
    this.accessToken = token;
    localStorage.setItem(STORAGE_KEY, token);
  }

  private isTokenValid(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }
}
