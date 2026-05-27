import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private accessToken: string | null = null;

  async login(username: string, password: string, rememberMe: boolean): Promise<void> {
    const res = await fetch('/auth/login', {
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
    this.accessToken = data.access_token;
  }

  async tryAutoLogin(): Promise<boolean> {
    try {
      const res = await fetch('/auth/refresh', { method: 'POST', credentials: 'include' });
      if (!res.ok) return false;
      const data = await res.json();
      this.accessToken = data.access_token;
      return true;
    } catch {
      return false;
    }
  }

  async logout(): Promise<void> {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
    this.accessToken = null;
  }

  getToken(): string | null {
    return this.accessToken;
  }

  isLoggedIn(): boolean {
    return this.accessToken !== null;
  }
}
