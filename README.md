# Data Pipeline & Visualization Stack

This repository provides a complete Dockerized setup for a **data pipeline and visualization dashboard**, consisting of a PostgreSQL database, a data-fetching/ETL service, a web-based dashboard, and a Cloudflare tunnel for secure remote access.

## 🚀 Services Overview

1. **Postgres (Database)**  
   - Stores raw and processed data.  
   - Data is persisted using a Docker volume (`postgres_data`).  

2. **Data Fetch (ETL Service)**  
   - Custom Python service (`./data_fetch/`).  
   - Fetches and processes external data.  
   - Loads results into the PostgreSQL database.  

3. **Data Viz (Dashboard)**  
   - Custom Python web dashboard (`./data_viz/`).  
   - Runs on **Gunicorn** with 4 workers.  
   - Exposed locally on [http://localhost:8050](http://localhost:8050).  

4. **Cloudflared Tunnel Service (Optional) **  
   - Provides secure remote access to the dashboard.  
   - Uses your Cloudflare account and tunnel configuration (`./cloudflared/config.yml`).  



## ⚙️ Setup & Usage

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (>= 20.10)  
- [Docker Compose](https://docs.docker.com/compose/install/) (v2 recommended)  
- A [Cloudflare account](https://dash.cloudflare.com/) with a configured tunnel (optional)

### 2. Environment Variables and cloudflare setup
Input credentials in .env (see exemplary file)

The `cloudflared` container expects a config file at `./cloudflared/config.yml` as follows

```yaml
tunnel: <YOUR_TUNNEL_ID>
credentials-file: /etc/cloudflared/<YOUR_TUNNEL_ID>.json

ingress:
  - hostname: mydashboard.example.com
    service: http://data_viz:8050
  - service: http_status:404
```

Note: if this part is not provided, the dashboard is still available locally. The cloudflare image throws some error that can be ignored


### 3. Build & Start the Stack
```bash
docker compose up --build
```


- PostgreSQL will be available inside the network as `postgres`.  
- Dashboard: [http://localhost:8050](http://localhost:8050).  
- Cloudflare tunnel will expose the dashboard at your configured Cloudflare domain.  

