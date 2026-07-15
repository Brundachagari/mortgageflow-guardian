# Private, encrypted bucket where fictional documents land.
# Security is layered on deliberately: a bucket is useless to an attacker if it
# blocks public access, encrypts at rest, and refuses non-HTTPS requests.

resource "aws_s3_bucket" "documents" {
  # Bucket names are globally unique, so we append the account id.
  bucket = "${local.name_prefix}-docs-${data.aws_caller_identity.current.account_id}"
}

# Block ALL forms of public access -- no accidental public files, ever.
resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encrypt every object at rest (server-side, AES-256).
resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Keep old versions so an accidental overwrite/delete is recoverable.
resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Refuse any request that isn't over HTTPS (encryption in transit).
resource "aws_s3_bucket_policy" "documents" {
  bucket = aws_s3_bucket.documents.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.documents.arn,
        "${aws_s3_bucket.documents.arn}/*"
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

# When a file is created under "incoming/", tell the SQS queue about it.
# This is the S3 -> SQS event that kicks off the whole pipeline.
resource "aws_s3_bucket_notification" "documents" {
  bucket = aws_s3_bucket.documents.id

  queue {
    queue_arn     = aws_sqs_queue.processing.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "incoming/"
  }

  # The queue must allow S3 to write to it before the notification is valid.
  depends_on = [aws_sqs_queue_policy.allow_s3]
}
