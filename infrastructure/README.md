# Analyez Infrastructure

Contains deployment scripts, Docker configurations, and infrastructure-as-code for Analyez.

## Deployment

Scripts in `deployment/` handle EC2 provisioning and updates.

- **`deploy.sh`**: Main deployment script for the Scraper/Data Engine.
- **`deploy_waitlist.sh`**: Deployment script for the Waitlist/Web App.
- **`create_ec2_package.py`**: Packages the codebase for upload.

## Docker

`docker/` contains `Dockerfile` for containerized deployment.
