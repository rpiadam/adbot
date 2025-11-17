'use client'

import Link from 'next/link'

export default function AuthError() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full mx-4">
        <h1 className="text-2xl font-bold text-center mb-4 text-red-600">
          Authentication Error
        </h1>
        <p className="text-center text-gray-600 mb-6">
          There was an error during authentication. Please try again.
        </p>
        <Link
          href="/auth/signin"
          className="block w-full text-center bg-primary-600 hover:bg-primary-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
        >
          Try Again
        </Link>
      </div>
    </div>
  )
}


