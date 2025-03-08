  function signupUser(type) {
    showNotification(`${type.charAt(0).toUpperCase() + type.slice(1)} signed up successfully!`);
    
    setTimeout(() => {
      window.location.href = "login.html";  // Redirect to login page
    }, 3000); // Wait 3 seconds before redirecting
  }
  
  function signupUser(type) {
    showNotification(`${type.charAt(0).toUpperCase() + type.slice(1)} signed up successfully!`);
  }
  

  function showNotification(message) {
    let popup = document.createElement("div");
    popup.className = "notification";
    popup.innerHTML = message;
    document.body.appendChild(popup);
  
    setTimeout(() => {
      popup.remove();
    }, 3000);
  }
  

  function loginUser(type) {
    showNotification(`${type.charAt(0).toUpperCase() + type.slice(1)} logged in successfully!`);
    
    if (type === 'patient') {
      window.location.href = 'patientProfile.html'; // Redirect to Patient Profile
    } else if (type === 'doctor') {
      window.location.href = 'doctorProfile.html'; // Redirect to Doctor Profile
    }
  }
  
  
  function addDoctorDetails() {
    let name = document.getElementById("doctor-name").value;
    let experience = `${document.getElementById("start-date").value} to ${document.getElementById("end-date").value}`;
    let specialization = document.getElementById("specialization").value;
    let contact = document.getElementById("contact").value;
    let email = document.getElementById("email").value;
    let address = document.getElementById("address").value;
  
    let doctor = { name, experience, specialization, contact, email, address };
    localStorage.setItem("doctorDetails", JSON.stringify(doctor));
    alert("Doctor Details Submitted!");
  }
  
  function showDoctors() {
    let list = document.getElementById("doctors-list");
    let doctor = JSON.parse(localStorage.getItem("doctorDetails"));
    if (doctor) {
      list.innerHTML = `
        <div>${doctor.name} - ${doctor.specialization} - ${doctor.address}</div>
      `;
    }
  }
  
  function searchDoctors() {
    let search = document.getElementById("search").value.toLowerCase();
    let list = document.getElementById("doctors-list");
    let doctor = JSON.parse(localStorage.getItem("doctorDetails"));
    if (doctor && doctor.name.toLowerCase().includes(search)) {
      list.innerHTML = `<div>${doctor.name} - ${doctor.specialization}</div>`;
    } else {
      list.innerHTML = "No doctors found.";
    }
  }
  function saveProfile() {
    let profile = {
      name: document.getElementById("profile-name").value,
      about: document.getElementById("profile-about").value,
      specialization: document.getElementById("profile-specialization").innerText,
      experience: `${document.getElementById("start-date").value} to ${document.getElementById("end-date").value}`,
      contact: document.getElementById("profile-contact").value,
      email: document.getElementById("profile-email").value,
      address: document.getElementById("profile-address").value
    };
  
    localStorage.setItem("doctorProfile", JSON.stringify(profile));
    alert("Profile Saved!");
    window.location.href = "index.html";
  }
  
  window.onload = function () {
    let profile = JSON.parse(localStorage.getItem("doctorProfile"));
    if (profile) {
      document.getElementById("profile-name").innerText = profile.name;
      document.getElementById("profile-about").value = profile.about;
      document.getElementById("profile-contact").value = profile.contact;
      document.getElementById("profile-email").value = profile.email;
      document.getElementById("profile-address").value = profile.address;
    }
  };
  
  function loadProfile() {
    let profile = JSON.parse(localStorage.getItem("doctorProfile"));
    if (profile) {
      document.getElementById("profile-name").value = profile.name;
      document.getElementById("profile-about").value = profile.about;
      document.getElementById("profile-specialization").value = profile.specialization;
      document.getElementById("profile-contact").value = profile.contact;
      document.getElementById("profile-email").value = profile.email;
      document.getElementById("profile-address").value = profile.address;
    }
  }
  
  function toggleMenu() {
    let dropdown = document.getElementById("menuDropdown");
    dropdown.classList.toggle("show");
  }
  
  window.onclick = function(event) {
    if (!event.target.matches('.menu-button')) {
      let dropdowns = document.getElementsByClassName("dropdown");
      for (let i = 0; i < dropdowns.length; i++) {
        dropdowns[i].classList.remove("show");
      }
    }
  };
  
  
  function toggleDarkMode() {
    document.body.classList.toggle("dark-mode");
    showNotification("Appearance Changed!");
  }
  
  function logout() {
    showNotification("Logged Out Successfully!");
    setTimeout(() => {
      window.location.href = "login.html";
    }, 2000);
  }
  

  if (window.location.pathname.includes("doctorProfile.html")) {
    window.onload = loadProfile;
  }
  
  
  function goBack() {
    window.history.back();
  }
  
  function goHome() {
    window.location.href = "index.html";
  }
  
  window.onload = function () {
    let navButtons = document.querySelector('.nav-buttons');
    if (!navButtons) {
      document.body.insertAdjacentHTML('afterbegin', `
        <div class="nav-buttons">
          <button onclick="goBack()">🔙 Back</button>
          <button onclick="goHome()">🏠 Home</button>
        </div>
      `);
    }
  };
  
  window.onload = function () {
    setTimeout(() => {
      document.getElementById("welcomePopup").style.display = "flex";
    }, 1000);
  };
  
  function closePopup() {
    document.getElementById("welcomePopup").style.display = "none";
  }

  function rateDoctor(event) {
    let stars = document.querySelectorAll('.stars span');
    let clickedStar = event.target;
    let index = Array.from(stars).indexOf(clickedStar) + 1;
  
    stars.forEach((star, i) => {
      if (i < index) {
        star.classList.add('clicked');
      } else {
        star.classList.remove('clicked');
      }
    });
  
    document.getElementById("rating-message").textContent = `You rated ${index} stars!`;
  }
  
  

  let sampleDoctors = [
    {
      name: "Dr. Rajesh Sharma",
      specialization: "Cardiologist",
      experience: "Jan 2010 to Dec 2023",
      contact: "9876543210",
      email: "rajesh.sharma@example.com",
      address: "Mumbai, India"
    },
    {
      name: "Dr. Priya Kapoor",
      specialization: "Dermatologist",
      experience: "Feb 2015 to Present",
      contact: "9876543211",
      email: "priya.kapoor@example.com",
      address: "Delhi, India"
    },
    {
      name: "Dr. Amit Kumar",
      specialization: "Neurologist",
      experience: "Mar 2012 to Present",
      contact: "9876543212",
      email: "amit.kumar@example.com",
      address: "Bangalore, India"
    }
  ];
  
  localStorage.setItem("sampleDoctors", JSON.stringify(sampleDoctors));
  
  function showDoctors() {
    let list = document.getElementById("doctors-list");
    let doctors = JSON.parse(localStorage.getItem("sampleDoctors")) || [];
    list.innerHTML = "";
    doctors.forEach((doctor, index) => {
      list.innerHTML += `
        <div class="card" onclick="viewDoctor(${index})">
          <h3>${doctor.name}</h3>
          <p>Specialization: ${doctor.specialization}</p>
          <p>Experience: ${doctor.experience}</p>
        </div>
      `;
    });
  }
  
  function viewDoctor(index) {
    localStorage.setItem("selectedDoctor", JSON.stringify(sampleDoctors[index]));
    window.location.href = "doctorDetails.html";
  }
  
  function searchDoctors() {
    let search = document.getElementById("search").value.toLowerCase();
    let filtered = sampleDoctors.filter(d =>
      d.name.toLowerCase().includes(search) || d.specialization.toLowerCase().includes(search)
    );
  
    let list = document.getElementById("doctors-list");
    list.innerHTML = "";
    filtered.forEach((doctor, index) => {
      list.innerHTML += `
        <div class="card" onclick="viewDoctor(${index})">
          <h3>${doctor.name}</h3>
          <p>Specialization: ${doctor.specialization}</p>
          <p>Experience: ${doctor.experience}</p>
        </div>
      `;
    });
  }
  
  function submitReview() {
    let review = document.getElementById("review-text").value;
    if (review) {
      let reviewList = document.getElementById("review-list");
      let newReview = document.createElement("p");
      newReview.textContent = review;
      reviewList.appendChild(newReview);
      document.getElementById("review-text").value = "";
      alert("Review Submitted!");
    } else {
      alert("Please write a review before submitting.");
    }
  }
  

  function showPopup(message) {
    let popup = document.createElement("div");
    popup.classList.add("popup");
    popup.innerHTML = `<div class="popup-content">${message}</div>`;
    document.body.appendChild(popup);
    setTimeout(() => popup.remove(), 2000);
  }

  function showDoctorLocation() {
    let map = L.map('map').setView([28.7041, 77.1025], 13); // Doctor Location (Delhi)
  
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);
  
    let doctorMarker = L.marker([28.7041, 77.1025]).addTo(map)
      .bindPopup('Doctor Location')
      .openPopup();
  
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(position => {
        let userLat = position.coords.latitude;
        let userLng = position.coords.longitude;
  
        let userMarker = L.marker([userLat, userLng]).addTo(map)
          .bindPopup('Your Location')
          .openPopup();
  
        let route = L.Routing.control({
          waypoints: [
            L.latLng(userLat, userLng),
            L.latLng(28.7041, 77.1025)
          ],
          routeWhileDragging: true
        }).addTo(map);
  
        route.on('routesfound', function (e) {
          let distance = e.routes[0].summary.totalDistance / 1000; // Convert meters to kilometers
          let time = Math.round(e.routes[0].summary.totalTime / 60); // Convert seconds to minutes
  
          if (distance > 100) {
            document.getElementById("route-info").innerHTML = "You are too far!";
          } else {
            document.getElementById("route-info").innerHTML = `Distance: ${distance.toFixed(2)} km<br>Estimated Time: ${time} mins`;
          }
        });
  
        route.on('routingerror', function () {
          document.getElementById("route-info").innerHTML = "You are too far!";
        });
      }, () => {
        alert("Unable to access your location");
      });
    } else {
      alert("Geolocation is not supported by your browser");
    }
  }
   
  function rateDoctor(event) {
    let stars = document.querySelectorAll('.star-rating span');
    let index = Array.from(event.target.parentNode.children).indexOf(event.target) + 1;
  
    stars.forEach((star, i) => {
      if (i < index) {
        star.style.color = 'gold';
      } else {
        star.style.color = '#ccc';
      }
    });
  }
 
  function savePatientProfile() {
    event.preventDefault();
    showNotification("Patient Profile Saved Successfully!");
  }
  
  function showAppointments() {
    let appointments = ["Consultation with Dr. Rajesh", "Follow-up with Dr. Amit"];
    let list = document.getElementById("appointment-list");
    list.innerHTML = "";
    appointments.forEach(app => {
      let li = document.createElement("li");
      li.textContent = app;
      list.appendChild(li);
    });
  }
  
  window.onload = showAppointments;
   
  function showTab(type) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.form').forEach(form => form.classList.remove('active'));
  
    document.querySelector(`.${type}-form`).classList.add('active');
    document.querySelector(`[onclick="showTab('${type}')"]`).classList.add('active');
  }
  

  
  