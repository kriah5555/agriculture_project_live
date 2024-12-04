
  
  // Simulated API data
  const apiData = {
    infoCards: [
      { title: "Notifications 10", icon: "fas fa-bell" },
      { title: "June 20th", subtitle: "SoilSaathi", value: "9 times called", icon:"" },
      { title: "22nd June", subtitle: "AtmoSense", value: "11 times called" },
      { title: "13th June", subtitle: "SoiLIFE", value: "2 items called" },
    ],
    mastitisData: {
      labels: ["13", "14", "15", "16",],
      datasets: [
        {
          label: "SoilSaathi",
          data: [7, 6, 6.5, 6.2],
          borderColor: "rgba(255, 99, 132, 1)",
        },
        {
          label: "AtmoSense",
          data: [6.5, 5.5, 6, 5.8],
          borderColor: "rgba(54, 162, 235, 1)",
        },
        {
          label: "SoiLIFE",
          data: [5, 5, 5.5, 5.5],
          borderColor: "rgba(255, 206, 86, 1)",
        },
      ],
    },
    milkInfo: [
      {
        label: "Soil saathi devise count",
        value: "Count 10",
        change: "20% Increase",
        changeType: "increase",
      },
      {
        label: "AtmoSense devise count",
        value: "Count 30",
        change: "15% Increase",
        changeType: "increase",
      },
      {
        label: "SoiLIFE",
        value: "Count 20",
        change: "5% Decrease",
        changeType: "decrease",
      },
    ],
    animalWellness: {
      labels: [
        "pH",
        "Solid Non Fat %",
        "Milk Fatty Acid %",
        "Total Protein %",
        "Lactose %",
        "Milk Fat %",
      ],
      data: [6.8, 9.7, 3.1, 2.9, 4.8, 3.6],
    },
  };
  
  const locationTypes = [
    {
      name: "Type A",
      color: "rgba(255, 99, 132, 0.8)",
      locations: [
        { lat: 40.7128, lng: -74.006 },
        { lat: 51.5074, lng: -0.1278 },
      ],
    },
    {
      name: "Type B",
      color: "rgba(54, 162, 235, 0.8)",
      locations: [
        { lat: 35.6762, lng: 139.6503 },
        { lat: 22.3193, lng: 114.1694 },
      ],
    },
    {
      name: "Type C",
      color: "rgba(255, 206, 86, 0.8)",
      locations: [
        { lat: -33.8688, lng: 151.2093 },
        { lat: -22.9068, lng: -43.1729 },
      ],
    },
  ];
  
  // Function to create an info card
  function createInfoCard(cardData) {
    const card = document.createElement("div");
    card.className = "col-md-3 mb-4";
    
    card.innerHTML = `
      <div class="card">
        <div class="card-body">
          ${
            cardData.icon
              ? `<div class="d-flex justify-content-between align-items-center" style="height: 100%;">
                  <h5 class="card-title">${cardData.title}</h5>
                  <i class="${cardData.icon} fa-2x"></i>
                </div>`
              : `
              <h3 class="card-title">${cardData.title}</h3>
              ${cardData.subtitle ? `<h2>${cardData.subtitle}</h2>` : ""}
              ${cardData.value ? `<p class="info_card_text">${cardData.value}</p>` : ""}`
          }
        </div>
      </div>
    `;
    
    return card;
  }
  
  // Function to create a chart card
  function createChartCard(id, title, chartType) {
    const card = document.createElement("div");
    card.className = "card";
    
    card.innerHTML = `
      <div class="card-body">
          <h5 class="card-title">${title}</h5>
          <canvas id="${id}" style="width: 100%; height: 300px;"></canvas>
      </div>
    `;
    
    return card;
  }
  
  // Function to create milk info card
  function createMilkInfoCard(milkInfoData) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-body">
          <h5 class="card-title">Milk Infographics</h5>
          ${milkInfoData
            .map(
              (info) => `
              <div class="row">
                <div class="milk-info col-md-12 p-2 border border-2 shadow-lg">
                    <p>${info.label}</p>
                    <h4>${info.value}</h4>
                    <span class="badge bg-${
                      info.changeType === "increase" ? "success" : "danger"
                    }">${info.change}</span>
                </div>
              </div>
          `
            )
            .join("")}
      </div>
    `;
    return card;
  }
  
  // Function to initialize charts
  function initializeChart(ctx, type, data, options) {
    return new Chart(ctx, {
      type: type,
      data: data,
      options: options,
    });
  }
  
  // Main function to render the dashboard
  async function renderDashboard() {
    Chart.register(ChartDataLabels);
  
    // Render info cards
    const infoCardsContainer = document.getElementById("infoCards");
    apiData.infoCards.forEach((cardData) => {
      infoCardsContainer.appendChild(createInfoCard(cardData));
    });
  
    // Render Mastitis chart
    const mastitisCard = document.getElementById("mastitisCard");
    mastitisCard.appendChild(
      createChartCard("mastitisChart", "Mastitis (June 13th - June 16th)", "line")
    );
  
    initializeChart(
      document.getElementById("mastitisChart").getContext("2d"),
      "line",
      apiData.mastitisData,
      {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
          },
        },
        plugins: {
          datalabels: {
            color: "",
            anchor: "end",
            align: "end",
            font: {
              weight: "bold",
              size: 12,
            },
            formatter: function (value) {
              return value;
            },
          },
        },
      }
    );
  
    // Render Milk Info card
    const milkInfoCard = document.getElementById("milkInfoCard");
    milkInfoCard.appendChild(createMilkInfoCard(apiData.milkInfo));
  
    // Render Animal Wellness chart
    const animalWellnessCard = document.getElementById("animalWellnessCard");
    animalWellnessCard.appendChild(
      createChartCard("animalWellnessChart", "Animal Wellness", "bar")
    );
  
    initializeChart(
      document.getElementById("animalWellnessChart").getContext("2d"),
      "bar",
      {
        labels: apiData.animalWellness.labels,
        datasets: [
          {
            label: "Values",
            data: apiData.animalWellness.data,
            backgroundColor: "rgba(75, 192, 192, 0.8)",
          },
        ],
      },
      {
        responsive: true,
        scales: { y: { beginAtZero: true } },
        plugins: {
          datalabels: {
            color: "#fff",
            anchor: "center",
            align: "center",
            font: {
              weight: "bold",
              size: 16,
            },
            formatter: function (value) {
              return value;
            },
          },
        },
      }
    );
  
    // Initialize the map
    const map = L.map('map').setView([0, 0], 2);
  
    // Add the OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);
  
    // Add markers for each location type
    locationTypes.forEach(type => {
      type.locations.forEach(loc => {
        L.circleMarker([loc.lat, loc.lng], {
          radius: 8,
          fillColor: type.color,
          color: "#000",
          weight: 1,
          opacity: 1,
          fillOpacity: 0.8
        }).addTo(map).bindPopup(`${type.name}: ${loc.lat}, ${loc.lng}`);
      });
    });
  }