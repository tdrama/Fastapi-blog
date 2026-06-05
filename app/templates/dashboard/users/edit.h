hhh{% extends "base.html" %}

{% block content %}

<!-- PAGE HEADER -->
<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">

    <div>
        <h1 class="text-3xl font-bold text-gray-800">
            Users Management
        </h1>

        <p class="text-gray-500 mt-1">
            Manage all registered users
        </p>
    </div>

    <a href="/auth/register"
       class="bg-black hover:bg-gray-800 text-white px-5 py-3 rounded-xl">
        + Add User
    </a>

</div>

<!-- ANALYTICS -->
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">

    <!-- TOTAL USERS -->
    <div class="bg-white rounded-2xl shadow-sm p-6">

        <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-500 font-medium">
                Total Users
            </h3>

            <span class="text-3xl">
                👥
            </span>
        </div>

        <h2 class="text-4xl font-bold text-black">
            {{ total_users }}
        </h2>

    </div>

    <!-- ACTIVE USERS -->
    <div class="bg-white rounded-2xl shadow-sm p-6">

        <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-500 font-medium">
                Active Users
            </h3>

            <span class="text-3xl">
                ✅
            </span>
        </div>

        <h2 class="text-4xl font-bold text-green-600">
            {{ active_users }}
        </h2>

    </div>

    <!-- DISABLED USERS -->
    <div class="bg-white rounded-2xl shadow-sm p-6">

        <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-500 font-medium">
                Disabled Users
            </h3>

            <span class="text-3xl">
                ❌
            </span>
        </div>

        <h2 class="text-4xl font-bold text-red-600">
            {{ disabled_users }}
        </h2>

    </div>

    <!-- ADMINS -->
    <div class="bg-white rounded-2xl shadow-sm p-6">

        <div class="flex items-center justify-between mb-4">
            <h3 class="text-gray-500 font-medium">
                Admins
            </h3>

            <span class="text-3xl">
                🛡️
            </span>
        </div>

        <h2 class="text-4xl font-bold text-purple-600">
            {{ admins }}
        </h2>

    </div>

</div>

<!-- USERS TABLE -->
<div class="bg-white rounded-2xl shadow-sm overflow-hidden">

    <!-- TABLE HEADER -->
    <div class="p-6 border-b">

        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">

            <div>
                <h2 class="text-2xl font-bold text-gray-800">
                    All Users
                </h2>

                <p class="text-gray-500 mt-1">
                    Registered users in your system
                </p>
            </div>

            <!-- SEARCH -->
            <div class="w-full md:w-80">

                <input
                    type="text"
                    id="searchInput"
                    placeholder="Search users..."
                    class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-black"
                >

            </div>

        </div>

    </div>

    <!-- TABLE -->
    <div class="overflow-x-auto">

        <table class="w-full min-w-[1000px]">

            <thead class="bg-gray-100">

                <tr>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        ID
                    </th>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        User
                    </th>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        Email
                    </th>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        Role
                    </th>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        Status
                    </th>

                    <th class="px-6 py-4 text-left text-sm font-bold text-gray-600">
                        Joined
                    </th>

                    <th class="px-6 py-4 text-center text-sm font-bold text-gray-600">
                        Actions
                    </th>

                </tr>

            </thead>

            <tbody id="usersTable">

                {% for user in users %}

                <tr class="border-b hover:bg-gray-50 transition">

                    <!-- ID -->
                    <td class="px-6 py-4 font-semibold text-gray-700">
                        #{{ user.id }}
                    </td>

                    <!-- USER -->
                    <td class="px-6 py-4">

                        <div class="flex items-center gap-4">

                            {% if user.profile_image %}

                            <img
                                src="{{ user.profile_image }}"
                                class="w-12 h-12 rounded-full object-cover"
                            >

                            {% else %}

                            <div class="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center text-lg">
                                👤
                            </div>

                            {% endif %}

                            <div>

                                <h3 class="font-bold text-gray-800">
                                    {{ user.username }}
                                </h3>

                                {% if user.is_super_admin %}
                                <span class="text-xs bg-black text-white px-2 py-1 rounded-full">
                                    Super Admin
                                </span>
                                {% endif %}

                            </div>

                        </div>

                    </td>

                    <!-- EMAIL -->
                    <td class="px-6 py-4 text-gray-700">
                        {{ user.email }}
                    </td>

                    <!-- ROLE -->
                    <td class="px-6 py-4">

                        {% if user.is_admin %}

                        <span class="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-sm font-medium">
                            Admin
                        </span>

                        {% else %}

                        <span class="bg-gray-100 text-gray-700 px-3 py-1 rounded-full text-sm font-medium">
                            User
                        </span>

                        {% endif %}

                    </td>

                    <!-- STATUS -->
                    <td class="px-6 py-4">

                        {% if user.is_active %}

                        <span class="bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm font-medium">
                            Active
                        </span>

                        {% else %}

                        <span class="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-medium">
                            Disabled
                        </span>

                        {% endif %}

                    </td>

                    <!-- CREATED -->
                    <td class="px-6 py-4 text-gray-600">

                        {% if user.created_at %}
                            {{ user.created_at.strftime('%d %b %Y') }}
                        {% endif %}

                    </td>

                    <!-- ACTIONS -->
                    <td class="px-6 py-4">

                        <div class="flex flex-wrap justify-center gap-2">

                            <!-- EDIT -->
                            <a href="/auth/user/edit/{{ user.id }}"
                               class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-2 rounded-lg text-sm">
                                Edit
                            </a>

                            <!-- TOGGLE STATUS -->
                            <a href="/auth/user/toggle-status/{{ user.id }}"
                               class="bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-2 rounded-lg text-sm">

                                {% if user.is_active %}
                                    Disable
                                {% else %}
                                    Activate
                                {% endif %}

                            </a>

                            <!-- TOGGLE ADMIN -->
                            <a href="/auth/user/toggle-admin/{{ user.id }}"
                               class="bg-purple-500 hover:bg-purple-600 text-white px-3 py-2 rounded-lg text-sm">

                                {% if user.is_admin %}
                                    Remove Admin
                                {% else %}
                                    Make Admin
                                {% endif %}

                            </a>

                            <!-- DELETE -->
                            <a href="/auth/user/delete/{{ user.id }}"
                               onclick="return confirm('Delete this user?')"
                               class="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-lg text-sm">
                                Delete
                            </a>

                        </div>

                    </td>

                </tr>

                {% endfor %}

            </tbody>

        </table>

    </div>

</div>

<!-- SEARCH SCRIPT -->
<script>

const searchInput = document.getElementById("searchInput");

searchInput.addEventListener("keyup", function() {

    let filter = searchInput.value.toLowerCase();

    let rows = document.querySelectorAll("#usersTable tr");

    rows.forEach(row => {

        let text = row.innerText.toLowerCase();

        if (text.includes(filter)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }

    });

});

</script>

{% endblock %}
