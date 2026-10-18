MATCH (:IncidentLab {id:$lab})-[:HAS_RUN]->(r:IncidentRun)-[:OBSERVED]->(o:IncidentObservation)
WHERE r.kind IN ['source_a','source_b'] AND r.status='complete'
OPTIONAL MATCH (o)-[:ABOUT]->(c:IncidentComponent)
RETURN r.id, r.kind, o.payload, c.name
