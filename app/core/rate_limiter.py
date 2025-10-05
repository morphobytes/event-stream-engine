"""
Redis-based Rate Limiter for Campaign Orchestration
Provides atomic counter operations with TTL for rate limiting compliance
"""
import redis
from typing import Optional, Tuple
from datetime import datetime, timedelta
import os


class RateLimiter:
    """
    Redis-based rate limiter with atomic operations
    Used to enforce Campaign.rate_limit_per_second constraints
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis connection for rate limiting"""
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://redis:6379/0')
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
    
    def check_and_increment(self, campaign_id: int, rate_limit: int) -> Tuple[bool, int, int]:
        """
        Atomically check rate limit and increment counter if allowed
        
        Args:
            campaign_id: Campaign ID for rate limiting scope
            rate_limit: Maximum messages per second allowed
            
        Returns:
            Tuple of (allowed: bool, current_count: int, remaining_capacity: int)
        """
        # Use campaign-specific key with current second timestamp
        current_second = int(datetime.utcnow().timestamp())
        rate_key = f"campaign:{campaign_id}:rate_limit:{current_second}"
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        
        try:
            # Watch the key for changes during transaction
            pipe.watch(rate_key)
            
            # Get current count
            current_count = pipe.get(rate_key)
            current_count = int(current_count) if current_count else 0
            
            # Check if rate limit would be exceeded
            if current_count >= rate_limit:
                return False, current_count, 0
            
            # Start transaction
            pipe.multi()
            
            # Increment counter and set TTL (expires after 2 seconds to be safe)
            pipe.incr(rate_key)
            pipe.expire(rate_key, 2)
            
            # Execute transaction
            result = pipe.execute()
            
            new_count = result[0] if result else current_count + 1
            remaining = max(0, rate_limit - new_count)
            
            return True, new_count, remaining
            
        except redis.WatchError:
            # Key was modified during transaction, retry once
            return self.check_and_increment(campaign_id, rate_limit)
        
        except Exception as e:
            # Log error and allow message (fail open for reliability)
            print(f"Rate limiter error for campaign {campaign_id}: {e}")
            return True, 0, rate_limit
    
    def get_current_rate(self, campaign_id: int) -> int:
        """
        Get current message count for the current second
        
        Args:
            campaign_id: Campaign ID to check
            
        Returns:
            Current message count for this second
        """
        current_second = int(datetime.utcnow().timestamp())
        rate_key = f"campaign:{campaign_id}:rate_limit:{current_second}"
        
        try:
            count = self.redis_client.get(rate_key)
            return int(count) if count else 0
        except Exception:
            return 0
    
    def reset_rate_limit(self, campaign_id: int) -> bool:
        """
        Reset rate limit counter for campaign (for testing/admin purposes)
        
        Args:
            campaign_id: Campaign ID to reset
            
        Returns:
            True if successful
        """
        try:
            current_second = int(datetime.utcnow().timestamp())
            rate_key = f"campaign:{campaign_id}:rate_limit:{current_second}"
            self.redis_client.delete(rate_key)
            return True
        except Exception as e:
            print(f"Failed to reset rate limit for campaign {campaign_id}: {e}")
            return False
    
    def get_rate_limit_status(self, campaign_id: int, rate_limit: int) -> dict:
        """
        Get detailed rate limit status for monitoring
        
        Args:
            campaign_id: Campaign ID to check
            rate_limit: Configured rate limit
            
        Returns:
            Dict with rate limit status details
        """
        current_count = self.get_current_rate(campaign_id)
        
        return {
            'campaign_id': campaign_id,
            'current_second': int(datetime.utcnow().timestamp()),
            'rate_limit': rate_limit,
            'current_count': current_count,
            'remaining_capacity': max(0, rate_limit - current_count),
            'utilization_percent': round((current_count / rate_limit) * 100, 2) if rate_limit > 0 else 0,
            'is_throttled': current_count >= rate_limit
        }


# Global instance for use across the application
rate_limiter = RateLimiter()