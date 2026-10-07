update public.interviews
set korean_summary = replace(korean_summary, E'\\n', E'\n')
where source_hash is null;
