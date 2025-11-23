# frozen_string_literal: true

require_relative 'ruby_bot/version'
require_relative 'ruby_bot/config'
require_relative 'ruby_bot/storage'
require_relative 'ruby_bot/relay'
require_relative 'ruby_bot/auth'
require_relative 'ruby_bot/api'

module RubyBot
  # Main entry point for Ruby bot
  class Main
    def self.run
      config = Config.new
      coordinator = RelayCoordinator.new(config)
      
      # Start API server in background thread
      api_thread = Thread.new do
        begin
          api = API.new(coordinator: coordinator, settings: config)
          api.set :port, config.api_port
          api.set :bind, config.api_host
          api.run!
        rescue StandardError => e
          Logger.new($stderr).error("API server error: #{e}")
        end
      end
      
      # Start IRC in background threads
      coordinator.start_irc
      
      # Setup signal handlers
      Signal.trap('INT') do
        puts "\nShutting down..."
        coordinator.shutdown
        api_thread.kill if api_thread.alive?
        exit
      end
      
      Signal.trap('TERM') do
        puts "\nShutting down..."
        coordinator.shutdown
        api_thread.kill if api_thread.alive?
        exit
      end
      
      # Start Discord (blocks until shutdown)
      coordinator.start_discord
    end
  end
end

