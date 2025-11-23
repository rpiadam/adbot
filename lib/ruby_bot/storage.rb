# frozen_string_literal: true

require 'json'
require 'fileutils'
require 'logger'

module RubyBot
  # Persistent configuration store
  class Storage
    attr_reader :config_path

    def initialize(config_path = nil)
      @config_path = config_path || File.join(Dir.pwd, 'data', 'config_state.json')
      @lock = Mutex.new
      @data = {}
      
      FileUtils.mkdir_p(File.dirname(@config_path))
      load
    end

    # Monitor URLs
    def list_monitor_urls
      @lock.synchronize { @data[:monitor_urls] || [] }
    end

    def add_monitor_url(url)
      @lock.synchronize do
        @data[:monitor_urls] ||= []
        return false if @data[:monitor_urls].include?(url.strip)
        @data[:monitor_urls] << url.strip
        persist
        true
      end
    end

    def remove_monitor_url(url)
      @lock.synchronize do
        @data[:monitor_urls] ||= []
        return false unless @data[:monitor_urls].include?(url.strip)
        @data[:monitor_urls].delete(url.strip)
        persist
        true
      end
    end

    # RSS Feeds
    def list_rss_feeds
      @lock.synchronize { @data[:rss_feeds] || [] }
    end

    def add_rss_feed(url)
      @lock.synchronize do
        @data[:rss_feeds] ||= []
        return false if @data[:rss_feeds].include?(url.strip)
        @data[:rss_feeds] << url.strip
        persist
        true
      end
    end

    def remove_rss_feed(url)
      @lock.synchronize do
        @data[:rss_feeds] ||= []
        return false unless @data[:rss_feeds].include?(url.strip)
        @data[:rss_feeds].delete(url.strip)
        persist
        true
      end
    end

    # Credits
    def get_credits(user_id)
      @lock.synchronize { @data[:credits]&.dig(user_id.to_s) || 0 }
    end

    def add_credits(user_id, amount)
      @lock.synchronize do
        @data[:credits] ||= {}
        key = user_id.to_s
        balance = (@data[:credits][key] || 0) + amount
        balance = 0 if balance < 0
        @data[:credits][key] = balance
        persist
        balance
      end
    end

    # Feature Flags
    def get_feature_flags
      @lock.synchronize do
        @data[:feature_flags] ||= {
          games: true,
          music: true,
          monitoring: true,
          rss: true,
          welcome: true,
          moderation: true,
          football: true
        }
      end
    end

    def set_feature_flag(feature, enabled)
      @lock.synchronize do
        @data[:feature_flags] ||= {}
        @data[:feature_flags][feature.to_sym] = enabled
        persist
        true
      end
    end

    def is_feature_enabled?(feature)
      get_feature_flags[feature.to_sym] || false
    end

    # Moderation logs
    def add_moderation_log(log_entry)
      @lock.synchronize do
        @data[:moderation_logs] ||= []
        @data[:moderation_logs] << log_entry
        # Keep only last 1000 entries
        @data[:moderation_logs] = @data[:moderation_logs].last(1000) if @data[:moderation_logs].length > 1000
        persist
      end
    end

    def get_moderation_logs(limit = 100)
      @lock.synchronize do
        logs = @data[:moderation_logs] || []
        logs.last(limit)
      end
    end

    private

    def load
      return unless File.exist?(@config_path)
      
      begin
        content = File.read(@config_path)
        loaded = JSON.parse(content, symbolize_names: true)
        @data = loaded
      rescue JSON::ParserError, Errno::ENOENT => e
        Logger.new($stderr).warn("Failed to load config: #{e}")
        @data = {}
      end
    end

    def persist
      @lock.synchronize do
        # Convert symbols to strings for JSON compatibility
        json_data = @data.transform_keys(&:to_s)
        File.write(@config_path, JSON.pretty_generate(json_data))
      end
    rescue StandardError => e
      Logger.new($stderr).error("Failed to persist config: #{e}")
    end
  end
end

