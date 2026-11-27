-- Share only daily character totals in the community feed. Never expose diary text or manuscript content.
ALTER TABLE public.writer_likes DROP CONSTRAINT IF EXISTS writer_likes_item_shape;
ALTER TABLE public.writer_likes DROP CONSTRAINT IF EXISTS writer_likes_item_type_check;
ALTER TABLE public.writer_likes ADD CONSTRAINT writer_likes_item_type_check
  CHECK (item_type = ANY (ARRAY['stats'::text, 'achievement'::text, 'productivity'::text]));
ALTER TABLE public.writer_likes ADD CONSTRAINT writer_likes_item_shape
  CHECK (
    (item_type = 'stats' AND achievement_id IS NULL)
    OR (item_type = 'achievement' AND achievement_id IS NOT NULL)
    OR (item_type = 'productivity' AND achievement_id IS NOT NULL)
  );
CREATE UNIQUE INDEX IF NOT EXISTS writer_likes_unique_productivity
  ON public.writer_likes (liker_id, target_user_id, achievement_id)
  WHERE item_type = 'productivity' AND achievement_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.get_writer_productivity_feed()
RETURNS TABLE(
  event_id bigint,
  user_id uuid,
  display_name text,
  avatar_url text,
  social_url text,
  donation_url text,
  achievement_id text,
  earned_at timestamptz,
  chars_written bigint,
  like_count bigint,
  liker_ids uuid[]
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
  WITH daily AS (
    SELECT dp.user_id, dp.progress_date, SUM(dp.chars_written)::bigint AS chars_written
    FROM public.daily_progress dp
    WHERE dp.progress_date >= CURRENT_DATE - 30
      AND dp.progress_date <= CURRENT_DATE
      AND dp.chars_written > 0
    GROUP BY dp.user_id, dp.progress_date
  )
  SELECT
    EXTRACT(EPOCH FROM (d.progress_date::timestamp AT TIME ZONE 'UTC'))::bigint,
    d.user_id,
    COALESCE(p.display_name, 'Автор'),
    p.avatar_url,
    p.social_url,
    p.donation_url,
    d.progress_date::text,
    d.progress_date::timestamp AT TIME ZONE 'UTC',
    d.chars_written,
    COALESCE(likes.like_count, 0),
    COALESCE(likes.liker_ids, ARRAY[]::uuid[])
  FROM daily d
  JOIN public.profiles p ON p.id = d.user_id
  JOIN public.writer_settings s ON s.user_id = d.user_id
  LEFT JOIN LATERAL (
    SELECT
      COUNT(*)::bigint AS like_count,
      ARRAY_AGG(wl.liker_id ORDER BY wl.created_at DESC) AS liker_ids
    FROM public.writer_likes wl
    WHERE wl.target_user_id = d.user_id
      AND wl.item_type = 'productivity'
      AND wl.achievement_id = d.progress_date::text
  ) likes ON true
  WHERE (SELECT auth.uid()) IS NOT NULL
    AND (
      d.user_id = (SELECT auth.uid())
      OR (
        s.show_stats_to_mutuals IS TRUE
        AND EXISTS (
          SELECT 1
          FROM public.writer_follows wf
          WHERE wf.follower_id = (SELECT auth.uid())
            AND wf.followed_id = d.user_id
        )
      )
    )
  ORDER BY d.progress_date DESC, d.user_id
  LIMIT 50;
$function$;

REVOKE ALL ON FUNCTION public.get_writer_productivity_feed() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.get_writer_productivity_feed() FROM anon;
GRANT EXECUTE ON FUNCTION public.get_writer_productivity_feed() TO authenticated;
