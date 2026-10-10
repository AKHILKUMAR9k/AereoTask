document.addEventListener("DOMContentLoaded", () => {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const uploadProgress = document.getElementById("uploadProgress");
  const resultsContainer = document.getElementById("resultsContainer");

  const metaFilename = document.getElementById("metaFilename");
  const metaFileId = document.getElementById("metaFileId");
  const metaCrs = document.getElementById("metaCrs");
  const metaFeatureCount = document.getElementById("metaFeatureCount");
  const metaStatus = document.getElementById("metaStatus");

  const kpiArea = document.getElementById("kpiArea");
  const kpiAreaHectares = document.getElementById("kpiAreaHectares");
  const kpiLength = document.getElementById("kpiLength");
  const kpiLengthKm = document.getElementById("kpiLengthKm");
  const kpiDistribution = document.getElementById("kpiDistribution");

  const measurementsBody = document.getElementById("measurementsBody");
  const btnCopyJson = document.getElementById("btnCopyJson");
  const btnDownloadGeoJson = document.getElementById("btnDownloadGeoJson");

  const btnSampleKml = document.getElementById("btnSampleKml");
  const btnSampleShp = document.getElementById("btnSampleShp");

  let currentMeasurementsData = null;

  // Dropzone interactions
  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  // Sample files click handlers
  btnSampleKml.addEventListener("click", async () => {
    try {
      const resp = await fetch("/samples/sample_survey.kml");
      if (!resp.ok) {
        alert("Sample file not generated yet. Uploading sample...");
        return;
      }
      const blob = await resp.blob();
      const file = new File([blob], "sample_survey.kml", { type: "application/vnd.google-earth.kml+xml" });
      handleFileUpload(file);
    } catch (e) {
      alert("Error loading sample KML: " + e.message);
    }
  });

  btnSampleShp.addEventListener("click", async () => {
    try {
      const resp = await fetch("/samples/sample_shapefile.zip");
      if (!resp.ok) {
        alert("Sample file not generated yet. Uploading sample...");
        return;
      }
      const blob = await resp.blob();
      const file = new File([blob], "sample_shapefile.zip", { type: "application/zip" });
      handleFileUpload(file);
    } catch (e) {
      alert("Error loading sample Shapefile: " + e.message);
    }
  });

  // Copy JSON action
  btnCopyJson.addEventListener("click", () => {
    if (!currentMeasurementsData) return;
    navigator.clipboard.writeText(JSON.stringify(currentMeasurementsData, null, 2))
      .then(() => {
        btnCopyJson.textContent = "✓ Copied!";
        setTimeout(() => {
          btnCopyJson.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copy JSON`;
        }, 2000);
      });
  });

  async function handleFileUpload(file) {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (ext !== ".zip" && ext !== ".kml") {
      alert("Please upload either a .zip containing a Shapefile or a .kml file.");
      return;
    }

    uploadProgress.classList.remove("hidden");
    const formData = new FormData();
    formData.append("file", file);

    try {
      // 1. Upload file
      const uploadResp = await fetch("/api/files/", {
        method: "POST",
        body: formData
      });

      if (!uploadResp.ok) {
        const errorData = await uploadResp.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const fileInfo = await uploadResp.json();

      // 2. Fetch measurements
      const measResp = await fetch(`/api/files/${fileInfo.id}/measurements/`);
      if (!measResp.ok) {
        throw new Error("Failed to retrieve measurements.");
      }

      const measData = await measResp.json();
      currentMeasurementsData = measData;
      renderResults(fileInfo, measData);

    } catch (error) {
      alert("Error: " + error.message);
    } finally {
      uploadProgress.classList.add("hidden");
      fileInput.value = "";
    }
  }

  function renderResults(fileInfo, measData) {
    // Populate Metadata
    metaFilename.textContent = fileInfo.filename;
    metaFileId.textContent = fileInfo.id;
    metaCrs.textContent = fileInfo.crs;
    metaFeatureCount.textContent = `${fileInfo.feature_count} features`;
    metaStatus.textContent = fileInfo.status;

    btnDownloadGeoJson.href = `/api/files/${fileInfo.id}/geojson/`;

    // Populate KPIs
    const summary = measData.summary || {};
    if (summary.total_area_sq_m !== null && summary.total_area_sq_m !== undefined) {
      kpiArea.textContent = `${Number(summary.total_area_sq_m).toLocaleString()} m²`;
      kpiAreaHectares.textContent = `${Number(summary.total_area_hectares).toFixed(4)} hectares (${Number(summary.total_area_sq_m / 1e6).toFixed(4)} km²)`;
    } else {
      kpiArea.textContent = "N/A";
      kpiAreaHectares.textContent = "No polygon features";
    }

    if (summary.total_length_m !== null && summary.total_length_m !== undefined) {
      kpiLength.textContent = `${Number(summary.total_length_m).toLocaleString()} m`;
      kpiLengthKm.textContent = `${Number(summary.total_length_km).toFixed(4)} km`;
    } else {
      kpiLength.textContent = "N/A";
      kpiLengthKm.textContent = "No linestring features";
    }

    // Geometry distribution tags
    kpiDistribution.innerHTML = "";
    if (summary.geometry_distribution) {
      Object.entries(summary.geometry_distribution).forEach(([type, count]) => {
        const span = document.createElement("span");
        span.className = "geom-tag";
        span.textContent = `${type}: ${count}`;
        kpiDistribution.appendChild(span);
      });
    }

    // Render table
    measurementsBody.innerHTML = "";
    measData.measurements.forEach((item) => {
      const row = document.createElement("tr");

      let valDisplay = "-";
      let breakdownDisplay = "";

      if (item.measurement_type === "area") {
        valDisplay = `<span class="val-bold">${Number(item.value).toLocaleString()}</span> <span class="val-unit">m²</span>`;
        if (item.details) {
          breakdownDisplay = `<div class="val-breakdown">${item.details.area_hectares || 0} ha • ${item.details.area_sq_km || 0} km²</div>`;
        }
      } else if (item.measurement_type === "length") {
        valDisplay = `<span class="val-bold">${Number(item.value).toLocaleString()}</span> <span class="val-unit">m</span>`;
        if (item.details) {
          breakdownDisplay = `<div class="val-breakdown">${item.details.length_km || 0} km</div>`;
        }
      } else {
        valDisplay = `<span class="val-unit">None required</span>`;
        if (item.details && item.details.message) {
          breakdownDisplay = `<div class="val-breakdown">${item.details.message}</div>`;
        }
      }

      const propsStr = item.properties && Object.keys(item.properties).length > 0 
        ? JSON.stringify(item.properties) 
        : "{}";

      row.innerHTML = `
        <td class="mono">#${item.feature_id}</td>
        <td><span class="pill-type pill-${item.geometry_type}">${item.geometry_type}</span></td>
        <td class="mono">${item.projected_crs || '<span class="text-dim">N/A</span>'}</td>
        <td>${item.measurement_type ? item.measurement_type.toUpperCase() : '<span class="text-dim">-</span>'}</td>
        <td>${valDisplay}${breakdownDisplay}</td>
        <td><div class="props-json" title="${propsStr.replace(/"/g, '&quot;')}">${propsStr}</div></td>
      `;

      measurementsBody.appendChild(row);
    });

    resultsContainer.classList.remove("hidden");
    resultsContainer.scrollIntoView({ behavior: "smooth" });
  }
});
