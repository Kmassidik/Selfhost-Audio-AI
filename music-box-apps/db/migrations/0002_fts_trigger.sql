-- 0002_fts_trigger.sql — keeps songs.search fed: title, style, lyrics and model,
-- lowercased and joined.
CREATE OR REPLACE FUNCTION songs_search_fill() RETURNS trigger AS $$
BEGIN
  NEW.search := lower(NEW.title || ' ' || NEW.style || ' ' || NEW.lyrics || ' ' || NEW.model);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER songs_search_update
BEFORE INSERT OR UPDATE OF title, style, lyrics, model ON songs
FOR EACH ROW EXECUTE FUNCTION songs_search_fill();
