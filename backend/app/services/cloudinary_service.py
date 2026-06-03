import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import os


class CloudinaryService:
    def __init__(self, app):
        cloudinary.config(
            cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
            api_key=app.config['CLOUDINARY_API_KEY'],
            api_secret=app.config['CLOUDINARY_API_SECRET']
        )
        self.upload_folder = app.config.get('CLOUDINARY_UPLOAD_FOLDER', 'convopilot_temp')
        self.logger = app.logger

    def upload_temp_file(self, file_path):
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="raw",
            folder=self.upload_folder
        )
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'resource_type': 'raw'
        }

    def download_file(self, url, destination_path):
        response = requests.get(url, stream=True)
        response.raise_for_status()
        os.makedirs(os.path.dirname(destination_path) or '.', exist_ok=True)
        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return destination_path

    def delete_file(self, public_id):
        cloudinary.uploader.destroy(public_id, resource_type="raw")

    def cleanup_temp_files(self, prefix="convopilot_temp"):
        try:
            result = cloudinary.api.resources_by_prefix(
                prefix,
                resource_type="raw",
                max_results=500
            )
            deleted = 0
            for resource in result.get('resources', []):
                public_id = resource['public_id']
                created_at = resource['created_at']
                cloudinary.uploader.destroy(public_id, resource_type="raw")
                deleted += 1
            if deleted:
                self.logger.info(f"Cleaned up {deleted} expired Cloudinary temp files")
            return deleted
        except Exception as e:
            self.logger.error(f"Cloudinary cleanup error: {e}")
            return 0

    def upload_file_object(self, file_obj, filename):
        result = cloudinary.uploader.upload(
            file_obj,
            resource_type="raw",
            folder=self.upload_folder,
            public_id=filename
        )
        return {
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'resource_type': 'raw'
        }
