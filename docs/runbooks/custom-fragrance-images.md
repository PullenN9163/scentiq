# Custom fragrance images

Members can upload, replace, and remove an image from their private custom fragrance detail page. Shared catalog images remain source managed.

## Request and storage boundary

The browser sends image bytes to the authenticated Next.js route `/api/fragrances/{id}/image`. Next.js forwards the member's session token to the internal API. Reads use the same authenticated route and return `Cache-Control: private, no-store`; private images bypass the Next.js image optimizer so the member's cookie accompanies the request.

The internal API requires the fragrance's `owner_user_id` to match the authenticated member. Unknown, shared, and another member's fragrance all return `404`. Uploads accept JPEG, PNG, or WebP up to 5 MB, verify the decoded format against the declared MIME type, and reject images above 20 million pixels. Accepted images are resized to fit 1600 × 1600 pixels and re-encoded as WebP without EXIF, XMP, or source text metadata.

Images are stored at `users/{user_id}/fragrances/{fragrance_id}/image.webp`. Azure Blob containers remain private. The API uses `DefaultAzureCredential` with the configured managed identity; neither account keys nor storage credentials are sent to the browser.

## Configuration

Azure uses the existing `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_CLIENT_ID`, and private `uploads` container. `CUSTOM_IMAGE_CONTAINER` can select a separately provisioned private container. The API identity needs Blob Data Contributor access to write and delete images.

Host development can set `LOCAL_CUSTOM_IMAGE_DIRECTORY` to an absolute directory outside the public repository. This fallback is enabled only for `development` and `test`; Azure configuration takes precedence. Without either storage configuration, image operations return `503 image_storage_unavailable`.

## Deletion and failure recovery

Image removal deletes the stored object and clears the fragrance's image reference. Account deletion and reconciliation delete all objects in the member's namespace before purging database records. A storage failure stops account purging so the webhook or reconciliation can retry safely.

Azure's configured soft-delete and version-retention policies still apply to deleted objects. Operators should include those retention windows in deletion policies and storage lifecycle management.

## Verification

`tests/test_fragrance_images.py` covers byte validation, metadata removal, ownership isolation, removal, and account cleanup. The web image-route tests cover authentication, mutation-origin validation, the upload bound, and private response caching. Deployment smoke tests should upload a custom image, replace it, verify the updated preview, confirm another member cannot retrieve it, and remove it.
