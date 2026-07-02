'use client'

import { signIn } from 'next-auth/react'

export const authProviders = {
  google: {
    id: 'google',
    name: 'Google',
    icon: 'Chrome',
    color: '#4285F4',
  },
  facebook: {
    id: 'facebook',
    name: 'Facebook',
    icon: 'Facebook',
    color: '#1877F2',
  },
}

export async function handleSocialSignIn(
  provider: string,
  callbackUrl: string = '/dashboard'
) {
  try {
    // Store provider preference
    localStorage.setItem('lastLoginProvider', provider)
    
    const result = await signIn(provider, {
      callbackUrl,
      redirect: false,
    })

    if (result?.error) {
      throw new Error(`Failed to sign in with ${provider}`)
    }

    return { success: true }
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    }
  }
}

export function getStoredProvider(): string | null {
  return localStorage.getItem('lastLoginProvider')
}

export function getStoredEmail(): string | null {
  return localStorage.getItem('userEmail')
}

export function clearAuthStorage() {
  localStorage.removeItem('lastLoginProvider')
  localStorage.removeItem('userEmail')
  localStorage.removeItem('authPromptShown')
}

export function shouldShowAutoPrompt(): boolean {
  const prompted = localStorage.getItem('authPromptShown')
  const hasProvider = localStorage.getItem('lastLoginProvider')
  
  // Show if user has used social login before or never prompted
  return !prompted || !!hasProvider
}
