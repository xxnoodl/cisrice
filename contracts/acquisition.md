# Acquisition contracts

Executable typed contracts live in backend/app/contracts; these are packaged with
the backend. Discovery exposes AcquisitionCandidate through its public application
service. Acquisition never mutates discovery entities. Identity exposes background
authorization through IdentityService.authorize_background.

Durable job payload v1 for acquisition.download is {"rights_id": "UUID"}.
Redis transports only the durable job UUID, never source URLs or credentials.
Workers use the immutable JobLease contract and public JobLifecycle service;
acquisition does not mutate operations entities.
Job payloads are immutable after creation. Completion is fenced by a current lease
and commits asset registration and SUCCEEDED in one database transaction.

Source media formats are local MP4/Matroska/WebM video, validated with ffprobe and
full FFmpeg decode. Canonical bytes are immutable. BrandAsset references own rights
decisions independently of globally deduplicated MediaObject content hashes.
