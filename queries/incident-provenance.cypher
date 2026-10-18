MATCH (l:IncidentLab {id:$lab})-[:HAS_RUN]->(consumer:IncidentRun)-[:CITED]->(o:IncidentObservation)
MATCH (l)-[:HAS_RUN]->(producer:IncidentRun)-[:OBSERVED]->(o)
RETURN consumer.id, consumer.kind, producer.id, producer.kind, o.id, o.action, o.payload
