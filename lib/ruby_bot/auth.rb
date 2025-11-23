# frozen_string_literal: true

require 'jwt'
require 'bcrypt'

module RubyBot
  # Dashboard authentication utilities
  module Auth
    EXPIRATION_HOURS = 24

    # Verify a password against a hash or plain text
    def self.verify_password(plain_password, stored_password)
      # Check if password is hashed (bcrypt hashes start with $2b$ or $2a$)
      if stored_password.start_with?('$2b$') || stored_password.start_with?('$2a$')
        BCrypt::Password.new(stored_password) == plain_password
      else
        # Plain text comparison (backwards compatibility)
        plain_password == stored_password
      end
    rescue StandardError
      false
    end

    # Hash a password using bcrypt
    def self.hash_password(password)
      BCrypt::Password.create(password).to_s
    end

    # Create a JWT access token
    def self.create_access_token(data, secret_key, expires_hours = EXPIRATION_HOURS)
      payload = data.merge(
        exp: Time.now.to_i + (expires_hours * 3600)
      )
      JWT.encode(payload, secret_key, 'HS256')
    end

    # Verify and decode a JWT token
    def self.verify_token(token, secret_key)
      decoded = JWT.decode(token, secret_key, true, { algorithm: 'HS256' })
      decoded[0] # Return payload
    rescue JWT::DecodeError, JWT::ExpiredSignature
      nil
    end

    # Authenticate a user against settings
    def self.authenticate_user(username, password, settings)
      return false unless settings.dashboard_username && settings.dashboard_password
      return false unless username == settings.dashboard_username

      verify_password(password, settings.dashboard_password)
    end

    # Extract token from Authorization header
    def self.extract_token(auth_header)
      return nil unless auth_header

      # Support "Bearer <token>" format
      match = auth_header.match(/Bearer\s+(.+)/i)
      match ? match[1] : nil
    end
  end
end

