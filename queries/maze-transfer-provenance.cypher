MATCH (e:Episode {seed:$seed})-[u:USED_LOCAL_RULE]->(r:LocalRule {id:$rule})
MATCH (r)-[s:SUPPORTED_BY]->(sample:LocalSample)-[v:OBSERVED_IN]->(o:Observation)
RETURN e,u,r,s,sample,v,o
LIMIT 8
