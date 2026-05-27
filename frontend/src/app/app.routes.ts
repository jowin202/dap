import { Routes } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from './services/auth.service';
import { Router } from '@angular/router';

function authGuard() {
  const auth   = inject(AuthService);
  const router = inject(Router);
  if (auth.isLoggedIn()) return true;
  return router.createUrlTree(['/login']);
}

export const routes: Routes = [
  { path: '', redirectTo: 'upload', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./components/login/login').then(m => m.LoginComponent),
  },
  {
    path: 'upload',
    loadComponent: () => import('./components/upload/upload').then(m => m.UploadComponent),
    canActivate: [authGuard],
  },
  {
    path: 'download',
    loadComponent: () => import('./components/download/download').then(m => m.DownloadComponent),
  },
  {
    path: 'download/:token',
    loadComponent: () => import('./components/download/download').then(m => m.DownloadComponent),
  },
  { path: '**', redirectTo: 'upload' },
];
