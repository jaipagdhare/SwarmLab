MATCH (r:LocalRule {id:$rule})-[:SUPPORTED_BY]->(s:LocalSample)-[:OBSERVED_IN]->(o:Observation)
RETURN r.id, r.status, s.payload, o.id, o.payload
